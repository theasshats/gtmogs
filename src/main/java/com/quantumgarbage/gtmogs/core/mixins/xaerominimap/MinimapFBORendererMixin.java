package com.quantumgarbage.gtmogs.core.mixins.xaerominimap;

import net.minecraft.client.Minecraft;

import com.quantumgarbage.gtmogs.config.ConfigHolder;
import com.quantumgarbage.gtmogs.integration.map.xaeros.minimap.ore.OreVeinElementRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import xaero.common.HudMod;
import xaero.common.minimap.MinimapProcessor;
import xaero.common.minimap.render.MinimapFBORenderer;
import xaero.common.minimap.render.MinimapRenderer;
import xaero.hud.minimap.Minimap;
import xaero.hud.minimap.compass.render.CompassRenderer;
import xaero.hud.minimap.element.render.map.MinimapElementMapRendererHandler;
import xaero.hud.minimap.waypoint.render.WaypointMapRenderer;

/**
 * Registers the ore-vein layer with the minimap's element render handlers.
 * Ported from GTCEu (GregTechCEu/GregTech-Modern, 1.21 branch, LGPL-3.0) —
 * upstream gtmogs kept the Xaero renderer classes but dropped GTCEu's
 * registration mixins, which left the whole Xaero integration unreachable.
 */
@Mixin(value = MinimapFBORenderer.class, remap = false)
public abstract class MinimapFBORendererMixin extends MinimapRenderer {

    @Shadow
    private MinimapElementMapRendererHandler minimapElementMapRendererHandler;

    public MinimapFBORendererMixin(HudMod modMain, Minecraft mc, WaypointMapRenderer waypointMapRenderer,
                                   Minimap minimap, CompassRenderer compassRenderer) {
        super(modMain, mc, waypointMapRenderer, minimap, compassRenderer);
    }

    @Inject(method = "loadFrameBuffer",
            at = @At(value = "INVOKE", target = "Lxaero/common/mods/SupportMods;worldmap()Z"))
    private void gtmogs$injectProspectionMarkers(MinimapProcessor minimapProcessor, CallbackInfo ci) {
        if (!ConfigHolder.INSTANCE.compat.minimap.toggle.xaerosMapIntegration) return;
        OreVeinElementRenderer renderer = OreVeinElementRenderer.Builder.begin().build();
        minimapElementMapRendererHandler.add(renderer);
        this.minimap.getOverMapRendererHandler().add(renderer);
    }
}
