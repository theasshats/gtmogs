#!/usr/bin/env python3
"""Exact expected-yield calculator for gtmogs classic veins.

Replicates the geometry and band logic of
``api/worldgen/generator/veins/ClassicVeinGenerator`` (as of 1.0.6-pcmc.x)
to compute, in closed form, the expected number of ore blocks a vein places
per band — assuming every candidate position is replaceable stone (the
solid-stone upper bound; carver caves, fluids, the surface, and other veins
reduce real counts, and ``discard_chance_on_air_exposure`` thins exposed
faces).

Mechanics being modeled (derived from the Java source, validated by the
built-in Monte Carlo of the same branch logic):

- ``R = cluster_size // 2`` (integer division), ``h = R // 2``.
- Candidate positions are the integer lattice points of an oblate spheroid
  x^2/R^2 + y^2/h^2 + z^2/R^2 <= 1 - 1/R^2, vertically TRUNCATED to
  ``|y| <= yMax`` where ``yMax = min(R, y_radius)``. The slab is
  ``2*yMax + 1`` layers tall; ``y_radius`` is a cap, not the vein height —
  the spheroid's intrinsic half-height is ``h``, set by cluster_size alone.
- Layer index ``L = y + yMax`` (0 = bottom). With band sizes p/s/b
  (primary/secondary/between; "sporadic" has no layer count):
  - secondary zone: ``L < s``; primary zone: ``L >= s`` — primary is
    UNBOUNDED above, so it owns every layer the slab has past the first s.
  - between band OVERLAYS layers ``s - b//2 .. s - b//2 + b - 1``
    (it straddles the secondary/primary boundary).
  - per-candidate rolls, in order: between at ``density/2`` (only inside
    its overlay), else primary-or-secondary (by zone) at ``density``, else
    sporadic at ``density / (p + s - 1)`` anywhere in the slab.

Usage:
  vein_yield.py --cluster-size 40 --density 0.3 [--y-radius 4]
                [--layers 3,3,2] [--per-layer] [--simulate N]
  vein_yield.py --json path/to/ore_vein.json [--per-layer] [--simulate N]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys


def layer_counts(cluster_size: int, y_radius: int) -> tuple[int, list[int]]:
    """Exact candidate count per layer, replicating the Java integer test."""
    R = cluster_size // 2
    h = R // 2
    if R <= 0 or h <= 0:
        return 0, []
    xy2 = R * R * h * h
    xz2 = R ** 4
    yz2 = h * h * R * R
    xyz2 = xy2 * R * R
    y_max = min(R, y_radius)

    counts = []
    for y in range(-y_max, y_max + 1):
        n = 0
        for x in range(-R, R + 1):
            xr = yz2 * x * x
            yr = xr + xz2 * y * y + xy2
            if yr > xyz2:
                continue
            zmax = math.isqrt((xyz2 - yr) // xy2)
            n += 2 * zmax + 1
        counts.append(n)
    return y_max, counts


def band_probabilities(L: int, density: float, p: int, s: int, b: int):
    """Per-candidate probabilities (primary, secondary, between, sporadic)."""
    divisor = p + s - 1
    start_between = s - b // 2
    in_between = start_between <= L <= start_between + b - 1

    p_between = density / 2 if in_between else 0.0
    fallthrough = 1.0 - p_between
    p_ps = fallthrough * density
    p_sporadic = fallthrough * (1.0 - density) * (density / divisor)
    if L >= s:
        return p_ps, 0.0, p_between, p_sporadic
    return 0.0, p_ps, p_between, p_sporadic


def expected_yield(cluster_size: int, density: float, y_radius: int,
                   p: int, s: int, b: int):
    y_max, counts = layer_counts(cluster_size, y_radius)
    bands = [0.0, 0.0, 0.0, 0.0]
    per_layer = []
    for L, n in enumerate(counts):
        probs = band_probabilities(L, density, p, s, b)
        per_layer.append((L, L - y_max, n, [n * x for x in probs]))
        for i, x in enumerate(probs):
            bands[i] += n * x
    return sum(counts), bands, per_layer


def simulate(cluster_size: int, density: float, y_radius: int,
             p: int, s: int, b: int, runs: int):
    """Monte Carlo of placeBlock()'s branch logic, for validating the math."""
    y_max, counts = layer_counts(cluster_size, y_radius)
    divisor = p + s - 1
    start_between = s - b // 2
    totals = [0, 0, 0, 0]
    rng = random.Random(0xC0FFEE)
    for _ in range(runs):
        for L, n in enumerate(counts):
            in_between = start_between <= L <= start_between + b - 1
            for _ in range(n):
                if in_between and rng.random() <= density / 2:
                    totals[2] += 1
                    continue
                if rng.random() <= density:
                    totals[0 if L >= s else 1] += 1
                    continue
                if rng.random() <= density / divisor:
                    totals[3] += 1
    return [t / runs for t in totals]


def from_json(path: str):
    with open(path) as f:
        data = json.load(f)
    cs = data["cluster_size"]
    if isinstance(cs, dict):
        if "value" in cs:
            cs = cs["value"]
        else:
            raise SystemExit(f"non-constant cluster_size in {path}: {cs} "
                             "(pass --cluster-size for distributions)")
    gen = data["generator"]
    if gen.get("type", "").split(":")[-1] != "classic":
        raise SystemExit(f"{path}: generator type {gen.get('type')!r} is not classic")
    # codec defaults: primary 4, secondary 3, between 3, y_radius 3
    layers = (gen.get("primary", {}).get("layers", 4),
              gen.get("secondary", {}).get("layers", 3),
              gen.get("between", {}).get("layers", 3))
    return (int(cs), float(data["density"]), int(gen.get("y_radius", 3)), layers)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", help="read cluster_size/density/y_radius/layers from a vein JSON")
    ap.add_argument("--cluster-size", type=int)
    ap.add_argument("--density", type=float)
    ap.add_argument("--y-radius", type=int, default=3,
                    help="codec default 3 (mod's builder default is 6)")
    ap.add_argument("--layers", default="4,3,3",
                    help="primary,secondary,between layer counts (codec defaults 4,3,3)")
    ap.add_argument("--per-layer", action="store_true")
    ap.add_argument("--simulate", type=int, metavar="N",
                    help="cross-check with N Monte Carlo vein instances")
    args = ap.parse_args()

    if args.json:
        cs, density, y_radius, (p, s, b) = from_json(args.json)
    else:
        if args.cluster_size is None or args.density is None:
            ap.error("--cluster-size and --density required without --json")
        cs, density, y_radius = args.cluster_size, args.density, args.y_radius
        p, s, b = (int(x) for x in args.layers.split(","))

    if s + p < b:
        raise SystemExit("invalid layers: between cannot exceed primary+secondary")

    R, h = cs // 2, (cs // 2) // 2
    candidates, bands, per_layer = expected_yield(cs, density, y_radius, p, s, b)
    total = sum(bands)
    y_max = min(R, y_radius)

    print(f"cluster_size={cs} density={density} y_radius={y_radius} layers={p}/{s}/{b}")
    print(f"shape: R={R} h={h} -> slab {2 * y_max + 1} layers tall, "
          f"{candidates} candidate positions (solid-stone upper bound)")
    names = ("primary", "secondary", "between", "sporadic")
    for name, val in zip(names, bands):
        share = 100 * val / total if total else 0
        print(f"  {name:<9} E[ore] = {val:8.1f}   ({share:4.1f}% of vein output)")
    print(f"  {'TOTAL':<9} E[ore] = {total:8.1f}   "
          f"(~{total / 64:.0f} stacks; {100 * total / candidates if candidates else 0:.1f}% of candidates)")

    if args.per_layer:
        print(" layer  y     candidates  primary secondary between sporadic")
        for L, y, n, vals in per_layer:
            print(f"  {L:>3} {y:>4} {n:>11}  " + " ".join(f"{v:8.1f}" for v in vals))

    if args.simulate:
        sim = simulate(cs, density, y_radius, p, s, b, args.simulate)
        print(f"monte carlo ({args.simulate} veins): " +
              " ".join(f"{n}={v:.1f}" for n, v in zip(names, sim)) +
              f" total={sum(sim):.1f}")


if __name__ == "__main__":
    main()
