# GTMOGS - GregTech Modern Ore Generation: Standalone

> **Maintained continuation.** This repository (`theasshats/gtmogs`) is a maintained
> continuation of [fmbellomy/gtmogs](https://github.com/fmbellomy/gtmogs) as of
> upstream 1.0.6, kept alive for the
> [Project Commonwealth](https://github.com/theasshats/project-commonwealth) pack.
> The license stays LGPL-3.0-only, the modid stays `gtmogs`, and all modified
> sources are published here with changes stated in commits and release notes.
> Working branch: `pcmc/main`; releases are tagged `1.0.6-pcmc.N` with main and
> sources jars attached. Upstream authorship and history are preserved unchanged.

## An Unfortunate Disclaimer
After having isolated the ore generation from GT:M I discovered that the KubeJS integration was broken - even in the original 1.21 branch of GT:M.
I have not been able to restore it in this mod, so to use this mod in your pack you'll have to either fork it and add the ores yourself to `data/worldgen/GTOreVeins.java` or find a way to generate the .json entries for each ore vein yourself.
Personally, I wrote a datagen script in KubeJS based on the OreVeinDefinitionBuilder class in this mod. If someone who knows more about datapack registries and making sure things get registered in the right order sees this and wants to help out, I would ***gladly*** accept a PR that fixes this.
After a week of slamming my head into this particular issue though I decided to just make a janky workaround and move on. It's worth it for that sweet, sweet GT ore generation though...


## Adding GTMOGS as a dependency

```groovy
// add maven repository
maven {
    name "com.quantumgarbage"
    url "https://maven.quantumgarbage.com/Releases"
}
// add as compile time dependency
// when in doubt, check https://maven.quantumgarbage.com/#/Releases/
compileOnly("com.quantumgarbage:gtmogs-${MC_VERSION}:${LATEST_VERSION}")
```

## The rest of the readme

Do you want to use GregTech's ore generation but not the *rest* of GregTech's absolutely enormous breadth of content? The time for celebration is upon you, my dearest pack developer.

For context, I put this together by cloning GT:M and just deleting everything that I could get rid of without breaking ore generation. Some very mild tweaking had to be done to oregen to unhook it from GT's custom ore system, and yet more mild tweaking had to be done to the map integrations to get those to work with conventional minecraft blocks.

As such, you can safely refer to [GTCEu's official documentation](https://gregtechceu.github.io/GregTech-Modern/Modpacks/Ore-Generation/) on ore generation for how to actually use this. 
(Assuming they don't massively overhaul oregen in the future and I never catch up. But that would never happen :clueless:)

## Features:
### Absolutely zero veins by default.
That's right. If you add this mod to a pack, it will then proceed to generate zero ores - *on top* of the default behavior of completely disabling vanilla ore generation. You will be oreless. After all, without GregTech's ore system, there's very little to make veins out of to begin with.

The expected use case is that this mod will be used almost exclusively by modpacks willing to implement their own ore veins that suit their specific needs.

_cough cough modern industrialization pack devs cough cough_

### EMI integration
In theory there should also be integration for JEI and REI, but I haven't tested those personally yet because I don't plan to use them. If you try using this with one of those mods and it doesn't work then make an issue and then I'll actually look into it.

### Map integration
This includes FTBChunks, JourneyMap, and Xaero's Mini/World Map (I also haven't tested Xaero's yet, so if it ends up being broken then put an issue here and I'll actually look at it.)

#### And a huge thanks to the devs behind GTCEu for the tremendous amount of work put into the base mod.
(Except for that I really am not doing this for the money, I just wanted cool ore veins because I'm a sigma.)