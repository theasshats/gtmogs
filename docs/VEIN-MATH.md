# Classic vein generator — exact yield math

Derived from `api/worldgen/generator/veins/ClassicVeinGenerator.java`,
`api/worldgen/ores/OreGenerator.java`, and `api/worldgen/ores/OreVeinUtil.java`
at `1.0.6-pcmc.1`. The closed-form model below is validated by a Monte Carlo of
the same branch logic (`tools/vein_yield.py --simulate`); the two agree to
within sampling noise.

`tools/vein_yield.py` computes everything here for a concrete vein:

```
python3 tools/vein_yield.py --json path/to/ore_vein/somevein.json --per-layer
python3 tools/vein_yield.py --cluster-size 40 --density 0.3 --y-radius 4 --layers 3,3,2
```

## 1. Geometry — what `cluster_size` and `y_radius` actually do

With `C = cluster_size` (sampled; constant in practice):

- horizontal radius `R = C ⌊/⌋ 2` (integer division: 35 and 34 both give 17),
- intrinsic vertical half-height `h = R ⌊/⌋ 2` — **set by cluster_size, not by
  `y_radius`**,
- candidate positions are the integer lattice points inside the oblate spheroid
  `x²/R² + y²/h² + z²/R² ≤ 1 − 1/R²`, **vertically truncated** to
  `|y| ≤ yMax = min(R, y_radius)`.

So `y_radius` is a *truncation cap*. For every pack-scale vein (`R ≥ 10`,
`y_radius = 4`) the body is a 9-layer slab cut from the middle of a much taller
spheroid; the slab's horizontal extent is the full `2R + 1` blocks at `y = 0`
and barely less at `|y| = 4`. Layer `L = y + yMax` counts from the slab bottom
(`L = 0`) to the top (`L = 2·yMax`). The candidate count per layer is
`N(L) ≈ π·(R² − 1 − y²·R²/h²)` (the tool computes it exactly).

Positions outside the world build height are skipped (only relevant if a
`height_range` lets the slab cross the world floor/ceiling).

## 2. Bands — the per-candidate rolls

Band layer counts come from the JSON (`layers` per band; codec defaults
primary 4 / secondary 3 / between 3; sporadic has no layer count — its
`layers` value is ignored). Derived constants:

```
sporadicDivisor = primary.layers + secondary.layers − 1
startPrimary    = secondary.layers
startBetween    = secondary.layers − between.layers ⌊/⌋ 2
```

Every candidate position rolls, in order (`d = density`):

1. **between** — only on layers `startBetween … startBetween + between.layers − 1`
   (a thin overlay straddling the secondary→primary boundary): place at `d/2`.
2. **primary or secondary** — on fall-through, place at `d`;
   primary if `L ≥ startPrimary`, secondary below. **The primary zone is
   unbounded above**: `primary.layers` never limits it — primary owns every
   layer from `startPrimary` to the top of the slab.
3. **sporadic** — on fall-through anywhere in the slab: place at
   `d / sporadicDivisor`.

Consequences that differ from the intuitive "bands are stacked slices" model:

- Bands **overlap**: a between-band candidate that fails its `d/2` roll still
  rolls primary/secondary at full `d`.
- The slab height comes from `y_radius`, the band boundary from
  `secondary.layers`; with 3/3/2 layers and a 9-layer slab, primary covers
  6 of 9 layers (~55% of vein output at pack densities), secondary 3 layers
  (~25%), between ~10%, sporadic ~10%. The naive 3/3/2/1 ⇒ 33/33/22/11 split
  is wrong on every band.
- Sporadic is a volume-wide thin spray (`d/5` with 3/3 layers), not a layer.
  At low density its share *exceeds* between's share (the `(1−d)` fall-through
  factor hurts it less), so "demote a byproduct from secondary to sporadic"
  is barely a demotion at `d ≈ 0.3` — *between* is the thin slot.
- Expected per-candidate yield (outside the between overlay) is
  `d + (1−d)·d/sporadicDivisor`; with the overlay it is
  `d/2 + (1 − d/2)·(d + (1−d)·d/sporadicDivisor)`.

## 3. What erodes the solid-stone upper bound

Each placement still requires the existing block to match a band target rule
(`stone_ore_replaceables` / `deepslate_ore_replaceables` in the usual dual-
target setup), so candidates inside carver caves, water/lava, structures, or
above the surface place nothing. Expect real counts at some fraction of the
upper bound depending on the Y band's cave/air density; the bound itself is
exact for fully solid ground.

`discard_chance_on_air_exposure` (`c`) then thins the cave/cliff skin:

- `c ≤ 0`: no air check at all — exposed ore places normally.
- `c ≥ 1`: every candidate adjacent to air (any of the 6 face neighbors) is
  discarded.
- `0 < c < 1`: the air check itself runs with probability `c`, so an exposed
  candidate survives with probability `1 − c`. Interior candidates are never
  affected.

RNG quirk, for completeness: the air-check roll is drawn from a fresh
`XoroshiroRandomSource` seeded with the same per-block seed as the band rolls,
so it *equals the block's first band roll* — for `0 < c < 1` the air check is
correlated with band membership (e.g. a between-band ore air-checks exactly
when its between roll was `< c`). Irrelevant at `c = 0` or `c = 1`.

## 4. Vein eligibility is sampled at y = 0, not at the vein's Y

`OreGenerator.createConfigs` → `OreVeinUtil.getVeinCenter` builds the anchor
center with `chunkPos.getMiddleBlockPosition(0)` — **y = 0** — and
`getEntries` samples `level.getUncachedNoiseBiome(...)` at that position
(`OreGenerator.java:113`). The vein's actual Y is sampled from `height_range`
*afterwards* (`computeVeinOrigin`), with a separately-jittered X/Z.

So eligibility is the 3D noise biome of the column at **y ≈ 0–3** (quart 0),
regardless of where the vein body ends up:

- a cave-biome pocket covering y 0–3 vetoes (or, for cave-tagged veins,
  captures) the anchor even for a vein whose body generates at y 90;
- a vein selected by the y-0 biome can still have its body land inside a cave
  pocket higher or lower in the column — that costs placement volume, not
  eligibility;
- anchor loss to cave pockets is therefore *uniform across veins*, set by
  pocket coverage at y 0–3 in the region — deep bands do not lose more
  anchors than shallow bands (they lose more *placement* volume to caves).

## 5. Worked example (pack-typical)

`cluster_size 40, density 0.3, y_radius 4, layers 3/3/2` →
`R = 20, h = 10`, 9-layer slab, 10,493 candidates:

| band | E[ore] | share |
|---|---|---|
| primary | 2,076 | 54.2% |
| secondary | 962 | 25.1% |
| between | 366 | 9.6% |
| sporadic | 425 | 11.1% |
| **total** | **3,829** | ~60 stacks |

Monte Carlo (200 simulated veins): 2,075.9 / 963.0 / 364.0 / 425.1 — agreement
to 0.3%.
