package com.quantumgarbage.gtmogs.integration.map;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.neoforged.neoforge.client.model.data.ModelData;

import com.mojang.blaze3d.systems.RenderSystem;
import com.quantumgarbage.gtmogs.api.worldgen.ores.GeneratedVeinMetadata;

public class MapIntegrationUtils {

    public static int getItemColor(Block b) {
        return b.defaultMapColor().col;
    }

    public static ResourceLocation getItemIcon(Block b) {
        return ResourceLocation.parse(BuiltInRegistries.BLOCK.getKey(b).toString());
    }

    public static TextureAtlasSprite getFirstBlockFace(Block b) {
        // The block's particle sprite is a single, always-present atlas sprite,
        // unlike per-face quads (which can be empty - the pcmc.7 crash - or, for
        // multi-element models, render as a smear of the atlas). Used only as the
        // flat fallback for a block with no item form.
        return Minecraft.getInstance().getBlockRenderer().getBlockModel(b.defaultBlockState())
                .getParticleIcon(ModelData.EMPTY);
    }

    /**
     * Draws a vein's marker icon centered on the current matrix origin, scaled to
     * {@code iconSize}. Renders the ore's actual item — a recognizable
     * inventory-style icon with true colors and no hand-rolled atlas UVs — and
     * falls back to the block's flat particle sprite only when the block has no
     * item form.
     */
    public static void renderVeinIcon(GuiGraphics graphics, Block block, int iconSize) {
        ItemStack stack = new ItemStack(block);
        if (!stack.isEmpty()) {
            var pose = graphics.pose();
            pose.pushPose();
            pose.translate(-iconSize / 2.0F, -iconSize / 2.0F, 200.0F);
            float scale = iconSize / 16.0F;
            pose.scale(scale, scale, 1.0F);
            graphics.renderItem(stack, 0, 0);
            pose.popPose();
            RenderSystem.setShaderColor(1, 1, 1, 1);
            return;
        }
        RenderSystem.setShaderColor(1, 1, 1, 1);
        graphics.blit(-iconSize / 2, -iconSize / 2, 200, iconSize, iconSize, getFirstBlockFace(block));
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
