# Adding ore veins (the way that actually works)

GTMOGS generates **zero veins out of the box** — it disables vanilla ore
generation and expects the pack to define its own veins. Upstream's README
("An Unfortunate Disclaimer") warns that the KubeJS *scripting* integration
for this is broken, and that is still true in this fork:

- **Broken: the KubeJS builder API.** A vein registered from a KubeJS script
  (`OreVeinDefinitionBuilder` through KubeJS registry events) appears to
  register — the script runs without errors — but never generates. Inherited
  from upstream (broken since GT:M's original 1.21 branch); fixing it is
  tracked on this repo's issue tracker.
- **Works: datapack JSON.** A vein defined as a JSON file in any datapack
  generates normally. If you use KubeJS, its virtual datapack is the easiest
  place to put the files — note these are plain *files under `kubejs/data/`*,
  not scripts.

## Where the file goes

```
<datapack>/data/<namespace>/gtmogs/ore_vein/<vein_name>.json
```

or, with KubeJS installed:

```
kubejs/data/<namespace>/gtmogs/ore_vein/<vein_name>.json
```

`<namespace>` is yours to choose (e.g. your pack's id). For 25 real,
in-production examples, see Project Commonwealth's vein files:
<https://github.com/theasshats/project-commonwealth/tree/v0.7.1/kubejs/data/pcmc/gtmogs/ore_vein>

## Minimal working example

```json
{
  "cluster_size": 32,
  "density": 0.4,
  "weight": 50,
  "layer": "stone",
  "dimension_filter": ["minecraft:overworld"],
  "height_range": {
    "height": {
      "type": "minecraft:uniform",
      "min_inclusive": { "absolute": -20 },
      "max_inclusive": { "absolute": 40 }
    }
  },
  "discard_chance_on_air_exposure": 0.0,
  "biomes": "#minecraft:is_overworld",
  "generator": {
    "type": "gtmogs:classic",
    "primary":   { "targets": [{ "target": { "predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables" }, "state": { "Name": "minecraft:iron_ore" } }], "layers": 3 },
    "secondary": { "targets": [{ "target": { "predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables" }, "state": { "Name": "minecraft:copper_ore" } }], "layers": 3 },
    "between":   { "targets": [{ "target": { "predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables" }, "state": { "Name": "minecraft:gold_ore" } }], "layers": 2 },
    "sporadic":  { "targets": [{ "target": { "predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables" }, "state": { "Name": "minecraft:redstone_ore" } }], "layers": 1 },
    "y_radius": 4
  }
}
```

Field notes:

- ⚠️ **The per-band key is `targets`, plural.** A singular `target` is valid
  JSON, loads as a datapack, and then **crashes world creation**. (The inner
  `target` key on each entry — the block predicate — is correct as singular.)
- For worlds with deepslate in the vein's y-band, give each band a second
  entry targeting `minecraft:deepslate_ore_replaceables` with the deepslate
  ore variant, or the vein will leave gaps below y0. See the Project
  Commonwealth examples.
- `density` is 0..1; `weight` is lottery tickets against other veins eligible
  in the same biome (relative, so it does nothing in a biome where only one
  vein is eligible). One vein anchor is attempted per
  `oreVeinGridSize`² chunks (config, default 3² = 9 chunks).
- Always set `biomes` (one biome tag). `#minecraft:is_overworld` means
  "everywhere in the overworld".
- Band mechanics and exact expected yields per `cluster_size`/`density`/
  `y_radius` are derived in [`VEIN-MATH.md`](VEIN-MATH.md); compute a vein's
  numbers with `tools/vein_yield.py --json your_vein.json`.

## Testing loop

1. Add the JSON, then **restart the world** (vein definitions are datapack
   registry data; don't rely on `/reload`).
2. `/gtmogs place_vein <namespace>:<vein_name>` — force-places the vein where
   you stand. If this works, your JSON is valid and registered; if the id
   doesn't tab-complete, the file didn't load (check the path and the log).
3. Veins only generate in **new** chunks. Fly out, then `/gtmogs census`
   counts what worldgen has recorded per vein type, and `/gtmogs prospect`
   force-reveals nearby recorded veins on your map.
4. Right-click a vein's ore block to prospect it normally; with Xaero's maps
   installed, toggle the ore-vein layer with the gtmogs button on the
   fullscreen map to see markers.
5. `dev.debugWorldgen: true` in `config/gtmogs.yaml` logs every placed vein to
   `debug.log`; the JEI "Ore Vein Diagram" shows each vein's composition
   in-game.
