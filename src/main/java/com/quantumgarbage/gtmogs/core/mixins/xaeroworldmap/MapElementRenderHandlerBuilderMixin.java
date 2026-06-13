package com.quantumgarbage.gtmogs.core.mixins.xaeroworldmap;

import com.quantumgarbage.gtmogs.config.ConfigHolder;
import com.quantumgarbage.gtmogs.integration.map.xaeros.worldmap.ore.OreVeinElementRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import xaero.map.element.MapElementRenderHandler;
import xaero.map.element.MapElementRenderer;

import java.util.List;

/**
 * Registers the ore-vein layer with the world map's element render handler.
 * Ported from GTCEu (GregTechCEu/GregTech-Modern, 1.21 branch, LGPL-3.0) —
 * upstream gtmogs kept the Xaero renderer classes but dropped GTCEu's
 * registration mixins, which left the whole Xaero integration unreachable.
 */
@Mixin(value = MapElementRenderHandler.Builder.class, remap = false)
public class MapElementRenderHandlerBuilderMixin {

    @ModifyVariable(method = "build", at = @At(value = "LOAD", ordinal = 3))
    private List<MapElementRenderer<?, ?, ?>> gtmogs$addOreRenderer(List<MapElementRenderer<?, ?, ?>> value) {
        if (ConfigHolder.INSTANCE.compat.minimap.toggle.xaerosMapIntegration) {
            value.add(OreVeinElementRenderer.Builder.begin().build());
        }
        return value;
    }
}
