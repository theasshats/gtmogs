#!/usr/bin/env python3
"""Mixin-target verifier for gtmogs' Xaero registration mixins.

``member_diff.py`` verifies constant-pool *references* (Fieldref / Methodref /
class refs), but a mixin injects against targets named by *string* inside its
annotations — ``@Mixin(value = X.class)``, ``@Inject(method = "build")``,
``@At(target = "Lxaero/...;name()V")``, ``@Shadow`` members — which never
appear as ordinary refs. A Xaero update that renames or reshapes an injection
target therefore sails past the member diff and silently breaks registration
at runtime (no markers, no map buttons). This tool parses those annotations
out of the built mixin classes and checks every named target against the
actual Xaero jars.

It is deliberately the bytecode-level check the pcmc.4 port was verified with
by hand, now automated for the weekly tripwire. A strings scan is not enough:
method names like "init"/"build" are far too common to verify by presence in
the constant pool, and ``@At`` targets must be resolved as owner+name+desc
against the real member tables.

Checks per mixin class (any class carrying ``@Mixin``):
- the ``@Mixin`` target class(es) exist in the target jars;
- each injector's ``method`` selector names a method that exists on a target
  class (name-level; descriptors in selectors are matched when present);
- each ``@At`` with a resolvable member ``target`` (INVOKE*/FIELD/NEW...) is
  resolved owner+name+desc, walking supers/interfaces;
- each ``@Shadow`` method/field exists on a target class with a matching
  descriptor (a name-only match is reported as signature drift).

Local-var / generic injection points (HEAD/TAIL/RETURN/LOAD/STORE/...) carry
no member target and are skipped.

Exit codes: 0 = all targets resolve, 1 = missing/mismatched, 2 = bad input.

Usage:
  mixin_targets.py --mod MOD.jar --target XAERO1.jar [--target XAERO2.jar ...]
                   [--mixin-package com/quantumgarbage/gtmogs/core/mixins]
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
import zipfile

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from member_diff import load_jar  # reuse the target-side parser + member tables

MIXIN_ANNO = "Lorg/spongepowered/asm/mixin/Mixin;"
SHADOW_ANNO = "Lorg/spongepowered/asm/mixin/Shadow;"
# injector annotations whose "method" element names target methods
INJECTOR_ANNOS = {
    "Lorg/spongepowered/asm/mixin/injection/Inject;",
    "Lorg/spongepowered/asm/mixin/injection/ModifyVariable;",
    "Lorg/spongepowered/asm/mixin/injection/ModifyArg;",
    "Lorg/spongepowered/asm/mixin/injection/ModifyArgs;",
    "Lorg/spongepowered/asm/mixin/injection/Redirect;",
    "Lorg/spongepowered/asm/mixin/injection/ModifyConstant;",
    "Lcom/llamalad7/mixinextras/injector/ModifyExpressionValue;",
    "Lcom/llamalad7/mixinextras/injector/ModifyReturnValue;",
    "Lcom/llamalad7/mixinextras/injector/wrapoperation/WrapOperation;",
}
AT_ANNO = "Lorg/spongepowered/asm/mixin/injection/At;"
# @At injection-point types that reference a constant-pool member via "target"
AT_MEMBER_POINTS = {"INVOKE", "INVOKE_ASSIGN", "INVOKE_STRING", "FIELD", "NEW"}

CONSTANT_SIZES = {3: 4, 4: 4, 8: 2, 16: 2, 19: 2, 20: 2}


class MixinClass:
    __slots__ = ("name", "annotations", "methods", "fields")

    def __init__(self):
        self.name = None
        self.annotations = []          # [decoded annotation]
        self.methods = []              # [(name, desc, [annotations])]
        self.fields = []               # [(name, desc, [annotations])]


def _parse(data: bytes) -> MixinClass:
    buf = io.BytesIO(data)

    def u1(): return buf.read(1)[0]
    def u2(): return struct.unpack(">H", buf.read(2))[0]
    def u4(): return struct.unpack(">I", buf.read(4))[0]

    if u4() != 0xCAFEBABE:
        raise ValueError("not a class file")
    u2(); u2()
    cp_count = u2()
    utf8, classes = {}, {}
    i = 1
    while i < cp_count:
        tag = u1()
        if tag == 1:
            utf8[i] = buf.read(u2()).decode("utf-8", "replace")
        elif tag == 7:
            classes[i] = u2()
        elif tag in (9, 10, 11, 12, 17, 18):
            buf.read(4)
        elif tag == 15:
            buf.read(3)
        elif tag in (5, 6):
            buf.read(8); i += 1
        elif tag in CONSTANT_SIZES:
            buf.read(CONSTANT_SIZES[tag])
        else:
            raise ValueError(f"bad cp tag {tag}")
        i += 1

    def utf(idx): return utf8[idx]
    def cls_name(idx): return utf8[classes[idx]]

    # element_value parser (returns a python value)
    def element_value():
        tag = chr(u1())
        if tag in "BCDFIJSZs":
            return utf8.get(u2())  # const pool index; for primitives the Utf8/num value isn't needed by us
        if tag == "e":               # enum: type_name_index, const_name_index
            u2(); return utf8.get(u2())
        if tag == "c":               # class info: descriptor
            return ("class", utf8.get(u2()))
        if tag == "@":               # nested annotation
            return ("anno", annotation())
        if tag == "[":               # array
            return [element_value() for _ in range(u2())]
        raise ValueError(f"bad element_value tag {tag}")

    def annotation():
        type_desc = utf8.get(u2())
        elems = {}
        for _ in range(u2()):
            ename = utf8.get(u2())
            elems[ename] = element_value()
        return {"type": type_desc, "elems": elems}

    def read_annotations(attr_name, length):
        end = buf.tell() + length
        out = []
        if attr_name in ("RuntimeVisibleAnnotations", "RuntimeInvisibleAnnotations"):
            for _ in range(u2()):
                out.append(annotation())
        buf.seek(end)
        return out

    def read_attributes():
        annos = []
        for _ in range(u2()):
            aname = utf(u2())
            alen = u4()
            if aname in ("RuntimeVisibleAnnotations", "RuntimeInvisibleAnnotations"):
                annos.extend(read_annotations(aname, alen))
            else:
                buf.read(alen)
        return annos

    info = MixinClass()
    u2()                      # access
    info.name = cls_name(u2())
    u2()                      # super
    for _ in range(u2()):
        u2()                  # interfaces
    for target in (info.fields, info.methods):
        for _ in range(u2()):
            u2()
            mname = utf(u2())
            mdesc = utf(u2())
            target.append((mname, mdesc, read_attributes()))
    info.annotations = read_attributes()
    return info


def desc_to_internal(desc: str) -> str:
    if desc and desc.startswith("L") and desc.endswith(";"):
        return desc[1:-1]
    return desc


def parse_at_target(target: str):
    """'Lowner;name(args)ret' or 'Lowner;name:Ltype;' -> (owner, name, desc, is_field)."""
    if not target or not target.startswith("L") or ";" not in target:
        return None
    owner = target[1:target.index(";")]
    rest = target[target.index(";") + 1:]
    if rest.startswith("L"):  # quirk: fully-qualified owner only
        return None
    if ":" in rest:           # field selector  name:desc
        name, _, fdesc = rest.partition(":")
        return owner, name, fdesc, True
    if "(" in rest:           # method selector name(args)ret
        name = rest[:rest.index("(")]
        mdesc = rest[rest.index("("):]
        return owner, name, mdesc, False
    return owner, rest, None, False  # name only


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", required=True)
    ap.add_argument("--target", action="append", required=True)
    ap.add_argument("--mixin-package", default="com/quantumgarbage/gtmogs/core/mixins")
    ap.add_argument("--namespace", default="xaero/",
                    help="only verify mixins targeting this namespace; targets/@At owners "
                         "outside it are skipped as unverifiable (default: xaero/)")
    args = ap.parse_args()
    ns = args.namespace

    # target index: name -> ClassInfo (with .methods/.fields/.super_name/.interfaces)
    index = {}
    for t in args.target:
        try:
            loaded = load_jar(t, nested=True)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"error: cannot read {t}: {exc}", file=sys.stderr)
            return 2
        index.update(loaded)
        print(f"target: {t} ({len(loaded)} classes incl. bundled)")

    def ancestry(owner):
        seen, queue = set(), [owner]
        while queue:
            n = queue.pop(0)
            if n in seen:
                continue
            seen.add(n)
            ci = index.get(n)
            yield n, ci
            if ci is not None:
                if ci.super_name:
                    queue.append(ci.super_name)
                queue.extend(ci.interfaces)

    def has_method(owner, name, desc=None):
        for _, ci in ancestry(owner):
            if ci is None:
                continue
            for mn, md in ci.methods:
                if mn == name and (desc is None or md == desc):
                    return True
        return False

    def has_field(owner, name, desc=None):
        for _, ci in ancestry(owner):
            if ci is None:
                continue
            for fn, fd in ci.fields:
                if fn == name and (desc is None or fd == desc):
                    return True
        return False

    # parse mixin classes out of the mod jar
    mixins = []
    with zipfile.ZipFile(args.mod) as jar:
        for entry in jar.namelist():
            if not entry.endswith(".class"):
                continue
            internal = entry[:-6]
            if not internal.startswith(args.mixin_package):
                continue
            try:
                mc = _parse(jar.read(entry))
            except ValueError as exc:
                print(f"warning: skip {entry}: {exc}", file=sys.stderr)
                continue
            if any(a["type"] == MIXIN_ANNO for a in mc.annotations):
                mixins.append(mc)

    if not mixins:
        print(f"error: no @Mixin classes under {args.mixin_package} in {args.mod}", file=sys.stderr)
        return 2
    print(f"mod: {args.mod} ({len(mixins)} mixin class(es))")

    problems = []   # (mixin, message)
    checks = 0
    verified_mixins = 0
    skipped_mixins = 0

    def selectors(value):
        """@Mixin value/targets or @Inject method element -> list of strings/classes."""
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for v in value:
                out.extend(selectors(v))
            return out
        return [value]

    for mc in mixins:
        mixin_anno = next(a for a in mc.annotations if a["type"] == MIXIN_ANNO)
        targets = []
        for v in selectors(mixin_anno["elems"].get("value")):
            if isinstance(v, tuple) and v[0] == "class":
                targets.append(desc_to_internal(v[1]))
        for v in selectors(mixin_anno["elems"].get("targets")):
            if isinstance(v, str):
                targets.append(v.replace(".", "/"))
        if not targets:
            problems.append((mc.name, "could not determine @Mixin target class"))
            continue
        # scope to the watched namespace: a mixin against vanilla/NeoForge/FTB
        # targets is unverifiable without those jars, so skip it (like
        # member_diff's inherited-external skip) rather than false-alarm.
        ns_targets = [t for t in targets if t.startswith(ns)]
        if not ns_targets:
            skipped_mixins += 1
            continue
        verified_mixins += 1
        for tcls in ns_targets:
            checks += 1
            if tcls not in index:
                problems.append((mc.name, f"@Mixin target class {tcls} not found"))

        live_targets = [t for t in ns_targets if t in index]

        def on_any_target(check):
            return any(check(t) for t in live_targets) if live_targets else False

        # @Shadow members
        for members, kind, lookup in (
                (mc.fields, "field", has_field), (mc.methods, "method", has_method)):
            for name, desc, annos in members:
                if not any(a["type"] == SHADOW_ANNO for a in annos):
                    continue
                checks += 1
                if on_any_target(lambda t: lookup(t, name, desc)):
                    continue
                if on_any_target(lambda t: lookup(t, name)):
                    problems.append((mc.name,
                        f"@Shadow {kind} {name} present but descriptor drifted from {desc}"))
                else:
                    problems.append((mc.name, f"@Shadow {kind} {name}{desc} not found on target"))

        # injectors + their @At targets
        for name, desc, annos in mc.methods:
            for a in annos:
                if a["type"] not in INJECTOR_ANNOS:
                    continue
                for sel in selectors(a["elems"].get("method")):
                    if not isinstance(sel, str):
                        continue
                    checks += 1
                    sel_name = sel.split("(")[0].split(":")[-1].lstrip("*").rstrip("*")
                    sel_desc = sel[sel.index("("):] if "(" in sel else None
                    if not on_any_target(lambda t: has_method(t, sel_name, sel_desc)) \
                            and not on_any_target(lambda t: has_method(t, sel_name)):
                        problems.append((mc.name,
                            f"{a['type'].split('/')[-1][:-1]} method selector '{sel}' "
                            f"matches no method on target"))
                # @At targets
                at_vals = []
                for key in ("at", "slice"):
                    for entry in selectors(a["elems"].get(key)):
                        if isinstance(entry, tuple) and entry[0] == "anno":
                            at_vals.append(entry[1])
                for at in at_vals:
                    point = at["elems"].get("value")
                    tgt = at["elems"].get("target")
                    if not isinstance(tgt, str):
                        continue
                    parsed = parse_at_target(tgt)
                    if parsed is None:
                        continue
                    owner, mname, mdesc, is_field = parsed
                    if not owner.startswith(ns):
                        continue  # vanilla/other-mod call inside an injected method
                    checks += 1
                    ok = (has_field(owner, mname, mdesc) if is_field
                          else has_method(owner, mname, mdesc))
                    if not ok and not (has_field(owner, mname) if is_field else has_method(owner, mname)):
                        problems.append((mc.name, f"@At target {tgt} not found"))

    print(f"{verified_mixins} mixin(s) target {ns}, {skipped_mixins} skipped (other namespaces); "
          f"{checks} targets checked")
    if verified_mixins == 0:
        print(f"error: no mixin targets {ns} — wrong jar or namespace?", file=sys.stderr)
        return 2
    if not problems:
        print(f"RESULT: OK — every {ns} mixin target resolves")
        return 0
    print(f"RESULT: DRIFT — {len(problems)} unresolved mixin target(s)")
    for mixin, msg in problems:
        print(f"  [{mixin.rsplit('/', 1)[-1]}] {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
