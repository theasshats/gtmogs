#!/usr/bin/env python3
"""Member-level verifier for gtmogs' references into the Xaero mods.

Parses every class file in the mod jar and extracts each Fieldref /
Methodref / InterfaceMethodref from the constant pool. Every reference
whose owner lives in the watched namespace (default ``xaero/``), or whose
owner is a mod class that inherits from a watched class, is resolved
against the *actual* field/method tables of the target jars, walking
superclasses and superinterfaces. Class references (constant-pool Class
entries, superclasses, interfaces) into the namespace are checked for
existence too.

Why not a strings scan: deleted field names persist in newer Xaero builds
as config-key string literals (e.g. ``"waypoints"`` in ModSettings), so
grepping for names false-passes. Only the constant pool + member tables
tell the truth. This is the failure mode that broke gtmogs 1.0.6 on
Xaero's World Map 1.40.0 (ModSettings.waypoints / .waypointBackgrounds /
.worldmapWaypointsScale deleted -> NoSuchFieldError in both map
integrations).

Resolution policy (tuned to avoid false alarms on a weekly cron):
- ref owner in namespace, member found while walking namespace classes -> OK
- ref owner in namespace, walk exhausts namespace ancestry without finding
  the member -> MISSING (this is the tripwire)
- walk escapes into classes we cannot see (Minecraft, JDK, ...) without
  finding the member -> SKIPPED (inherited-external; unverifiable here)
- referenced/extended namespace class absent from the target jars ->
  MISSING CLASS

Exit codes: 0 = everything resolves, 1 = missing members/classes,
2 = bad invocation or unreadable input.

Usage:
    member_diff.py --mod MOD.jar --target XAERO1.jar [--target XAERO2.jar ...]
                   [--namespace xaero/]
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
import zipfile
from collections import defaultdict

CONSTANT_SIZES = {
    3: 4,   # Integer
    4: 4,   # Float
    8: 2,   # String
    16: 2,  # MethodType
    19: 2,  # Module
    20: 2,  # Package
}


class ClassInfo:
    __slots__ = ("name", "super_name", "interfaces", "fields", "methods", "refs", "class_refs")

    def __init__(self):
        self.name = None
        self.super_name = None
        self.interfaces = []
        self.fields = set()    # {(name, descriptor)}
        self.methods = set()   # {(name, descriptor)}
        self.refs = []         # [(kind, owner, name, descriptor)]
        self.class_refs = set()


def parse_class(data: bytes) -> ClassInfo:
    buf = io.BytesIO(data)

    def u1():
        return buf.read(1)[0]

    def u2():
        return struct.unpack(">H", buf.read(2))[0]

    def u4():
        return struct.unpack(">I", buf.read(4))[0]

    if u4() != 0xCAFEBABE:
        raise ValueError("not a class file")
    u2()  # minor
    u2()  # major

    cp_count = u2()
    utf8 = {}
    classes = {}        # cp index -> name index
    name_and_type = {}  # cp index -> (name index, descriptor index)
    member_refs = []    # (tag, class index, name-and-type index)

    i = 1
    while i < cp_count:
        tag = u1()
        if tag == 1:
            length = u2()
            utf8[i] = buf.read(length).decode("utf-8", "replace")
        elif tag == 7:
            classes[i] = u2()
        elif tag in (9, 10, 11):
            member_refs.append((tag, u2(), u2()))
        elif tag == 12:
            name_and_type[i] = (u2(), u2())
        elif tag in (5, 6):
            buf.read(8)
            i += 1  # longs/doubles occupy two constant-pool slots
        elif tag == 15:
            buf.read(3)
        elif tag in (17, 18):
            buf.read(4)
        elif tag in CONSTANT_SIZES:
            buf.read(CONSTANT_SIZES[tag])
        else:
            raise ValueError(f"unknown constant pool tag {tag}")
        i += 1

    info = ClassInfo()
    u2()  # access_flags
    this_class = u2()
    super_class = u2()
    info.name = utf8[classes[this_class]]
    if super_class != 0:
        info.super_name = utf8[classes[super_class]]
    for _ in range(u2()):
        info.interfaces.append(utf8[classes[u2()]])

    def read_members(target: set):
        for _ in range(u2()):
            u2()  # access_flags
            name = utf8[u2()]
            desc = utf8[u2()]
            for _ in range(u2()):  # attributes
                u2()
                buf.read(u4())
            target.add((name, desc))

    read_members(info.fields)
    read_members(info.methods)

    kind_names = {9: "field", 10: "method", 11: "interfacemethod"}
    for tag, class_idx, nat_idx in member_refs:
        owner = utf8[classes[class_idx]]
        name_idx, desc_idx = name_and_type[nat_idx]
        info.refs.append((kind_names[tag], owner, utf8[name_idx], utf8[desc_idx]))

    for name_idx in classes.values():
        name = utf8[name_idx]
        # array class entries like "[Lxaero/map/Foo;" -> element type
        while name.startswith("["):
            name = name[1:]
        if name.startswith("L") and name.endswith(";"):
            name = name[1:-1]
        info.class_refs.add(name)

    return info


def _scan_zip(jar: zipfile.ZipFile, source: str, out: dict, nested: bool):
    for entry in jar.namelist():
        if nested and entry.startswith("META-INF/") and entry.endswith(".jar"):
            # jar-in-jar (e.g. Xaero's bundled xaero/lib common library):
            # those classes are present at runtime, so they belong in the index.
            with zipfile.ZipFile(io.BytesIO(jar.read(entry))) as inner:
                _scan_zip(inner, f"{source}!{entry}", out, nested)
            continue
        if not entry.endswith(".class") or entry.endswith("module-info.class"):
            continue
        name = entry
        if name.startswith("META-INF/versions/"):
            name = name.split("/", 3)[-1]  # merge multi-release variants
        try:
            parsed = parse_class(jar.read(entry))
        except ValueError as exc:
            print(f"warning: skipping unparseable {entry} in {source}: {exc}", file=sys.stderr)
            continue
        existing = out.get(parsed.name)
        if existing is None:
            out[parsed.name] = parsed
        else:  # multi-release/duplicate merge: union members, keep first hierarchy
            existing.fields |= parsed.fields
            existing.methods |= parsed.methods


def load_jar(path: str, nested: bool = False) -> dict[str, ClassInfo]:
    out: dict[str, ClassInfo] = {}
    with zipfile.ZipFile(path) as jar:
        _scan_zip(jar, path, out, nested)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", required=True, help="jar whose outgoing references are verified")
    ap.add_argument("--target", action="append", required=True,
                    help="jar providing the namespace classes (repeatable)")
    ap.add_argument("--namespace", default="xaero/",
                    help="internal-name prefix to verify against (default: xaero/)")
    args = ap.parse_args()
    ns = args.namespace

    try:
        # refs are collected from the mod's own (top-level) classes; its bundled
        # jar-in-jar libraries only join the index so inheritance walks resolve
        mod_classes = load_jar(args.mod)
        index = load_jar(args.mod, nested=True)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"error: cannot read {args.mod}: {exc}", file=sys.stderr)
        return 2
    for target in args.target:
        try:
            loaded = load_jar(target, nested=True)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"error: cannot read {target}: {exc}", file=sys.stderr)
            return 2
        index.update(loaded)
        print(f"target: {target} ({len(loaded)} classes incl. bundled)")
    print(f"mod: {args.mod} ({len(mod_classes)} classes)")

    def ancestry(owner: str):
        """Yield (class_name, info_or_None) over owner + supers + interfaces, BFS."""
        seen, queue = set(), [owner]
        while queue:
            name = queue.pop(0)
            if name in seen:
                continue
            seen.add(name)
            info = index.get(name)
            yield name, info
            if info is not None:
                if info.super_name:
                    queue.append(info.super_name)
                queue.extend(info.interfaces)

    def resolve(owner: str, member: tuple[str, str], is_field: bool):
        """-> ('ok'|'missing'|'external'), saw_namespace"""
        saw_ns = False
        external = False
        for name, info in ancestry(owner):
            in_ns = name.startswith(ns)
            saw_ns = saw_ns or in_ns
            if info is None:
                if in_ns:
                    return "missing", saw_ns  # namespace ancestor vanished outright
                if not name.startswith("java/"):
                    external = True  # unverifiable non-JDK ancestor (e.g. Minecraft)
                continue
            if member in (info.fields if is_field else info.methods):
                return "ok", saw_ns
        return ("external" if external else "missing"), saw_ns

    missing = defaultdict(set)    # (kind, owner, name, desc) -> {referencing classes}
    missing_classes = defaultdict(set)
    counts = {"ok": 0, "external": 0}
    relevant_classes = set()

    for cls in mod_classes.values():
        # 1. namespace classes referenced/extended must exist
        candidates = set(cls.class_refs)
        candidates.update(cls.interfaces)
        if cls.super_name:
            candidates.add(cls.super_name)
        for ref in candidates:
            if ref.startswith(ns):
                relevant_classes.add(cls.name)
                if ref not in index:
                    missing_classes[ref].add(cls.name)

        # 2. member references
        for kind, owner, name, desc in cls.refs:
            if owner.startswith(ns):
                pass  # direct namespace reference: always verify
            elif owner in mod_classes and any(
                    n.startswith(ns) for n, _ in ancestry(owner)):
                pass  # self-owned ref that can only resolve through namespace ancestry
            else:
                continue
            relevant_classes.add(cls.name)
            state, saw_ns = resolve(owner, (name, desc), kind == "field")
            if state == "ok" or not saw_ns:
                counts["ok"] += 1
            elif state == "external":
                counts["external"] += 1
            else:
                missing[(kind, owner, name, desc)].add(cls.name)

    print(f"classes referencing {ns}: {len(relevant_classes)}")
    print(f"member references verified: {counts['ok']} resolved, "
          f"{counts['external']} inherited-external (skipped)")

    if not missing and not missing_classes:
        print("RESULT: OK — every namespace reference resolves")
        return 0

    print(f"RESULT: DRIFT — {len(missing)} missing member(s), "
          f"{len(missing_classes)} missing class(es)")
    for ref, users in sorted(missing_classes.items()):
        print(f"  MISSING CLASS {ref}")
        for user in sorted(users):
            print(f"    referenced by {user}")
    for (kind, owner, name, desc), users in sorted(missing.items()):
        print(f"  MISSING {kind.upper()} {owner}.{name}:{desc}")
        for user in sorted(users):
            print(f"    referenced by {user}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
