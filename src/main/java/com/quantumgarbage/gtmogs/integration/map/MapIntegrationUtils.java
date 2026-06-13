package com.quantumgarbage.gtmogs.integration.map;

import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.Block;

import com.quantumgarbage.gtmogs.api.worldgen.ores.GeneratedVeinMetadata;

public class MapIntegrationUtils {

    public static int getItemColor(Block b) {
        return b.defaultMapColor().col;
    }

    public static ResourceLocation getItemIcon(Block b) {
        return ResourceLocation.parse(BuiltInRegistries.BLOCK.getKey(b).toString());
    }

    public static TextureAtlasSprite getFirstBlockFace(Block b) {
        RandomSource random = RandomSource.create();
        var state = b.defaultBlockState();
        var model = Minecraft.getInstance().getBlockRenderer().getBlockModel(state);
        // A block model's quads can live under the general (null) direction
        // (cross models, custom-parent ores, non-solid render types) OR under a
        // cull face. Asking only for NORTH and calling getFirst() throws
        // NoSuchElementException for any model that has no north-face quad, which
        // crashed the map marker render. Try general quads, then every face, then
        // fall back to the model's particle sprite (always present).
        var quads = model.getQuads(state, null, random);
        if (quads.isEmpty()) {
            for (Direction dir : Direction.values()) {
                quads = model.getQuads(state, dir, random);
                if (!quads.isEmpty()) break;
            }
        }
        return quads.isEmpty() ? model.getParticleIcon() : quads.getFirst().getSprite();
    }

    public static String veinCenter(GeneratedVeinMetadata vein) {
        StringBuilder sb = new StringBuilder();
        sb.append("[");
        sb.append(String.format("%2s", vein.center().getX()));
        sb.append(", ");
        sb.append(String.format("%2s", vein.center().getY()));
        sb.append(", ");
        sb.append(String.format("%2s", vein.center().getZ()));
        sb.append("]");
        return sb.toString();
    }
}
