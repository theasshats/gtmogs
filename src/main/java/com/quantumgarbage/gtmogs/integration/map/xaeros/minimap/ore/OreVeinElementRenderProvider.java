package com.quantumgarbage.gtmogs.integration.map.xaeros.minimap.ore;

import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;

import com.quantumgarbage.gtmogs.integration.map.xaeros.XaerosRenderer;
import xaero.hud.minimap.element.render.MinimapElementRenderLocation;
import xaero.hud.minimap.element.render.MinimapElementRenderProvider;

import java.util.Iterator;

public class OreVeinElementRenderProvider extends MinimapElementRenderProvider<OreVeinElement, OreVeinElementContext> {

    private Iterator<OreVeinElement> iterator;

    public OreVeinElementRenderProvider() {}

    @Override
    public void begin(MinimapElementRenderLocation location, OreVeinElementContext context) {
        // Xaero's World Map 1.40.0 removed ModSettings.waypoints; the vein layer has
        // its own visibility toggle, so render unconditionally.
        ResourceKey<Level> currentDim = Minecraft.getInstance().level.dimension();
        this.iterator = XaerosRenderer.oreElements.row(currentDim).values().iterator();
    }

    @Override
    public boolean hasNext(MinimapElementRenderLocation location, OreVeinElementContext context) {
        return this.iterator != null && this.iterator.hasNext();
    }

    @Override
    public OreVeinElement getNext(MinimapElementRenderLocation location, OreVeinElementContext context) {
        return this.iterator.next();
    }

    @Override
    public void end(MinimapElementRenderLocation location, OreVeinElementContext context) {}
}
