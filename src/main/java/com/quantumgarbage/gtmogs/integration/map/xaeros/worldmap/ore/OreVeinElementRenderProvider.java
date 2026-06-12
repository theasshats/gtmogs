package com.quantumgarbage.gtmogs.integration.map.xaeros.worldmap.ore;


import com.quantumgarbage.gtmogs.integration.map.xaeros.XaerosRenderer;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;

import xaero.map.WorldMap;
import xaero.map.element.MapElementRenderProvider;

import java.util.Iterator;

public class OreVeinElementRenderProvider extends MapElementRenderProvider<OreVeinElement, OreVeinElementContext> {

    private Iterator<OreVeinElement> iterator;

    public OreVeinElementRenderProvider() {}

    public void begin(int location, OreVeinElementContext context) {
        // Xaero's World Map 1.40.0 removed ModSettings.waypoints and
        // ModSettings.worldmapWaypointsScale (waypoint settings left the world map).
        // The vein layer has its own visibility toggle, so render unconditionally
        // and use a fixed 1.0 element scale.
        ResourceKey<Level> currentDim = Minecraft.getInstance().level.dimension();
        this.iterator = XaerosRenderer.oreElements.row(currentDim).values()
                .stream()
                .map(element -> new OreVeinElement(element.getVein(), element.getName()))
                .iterator();
        context.worldmapWaypointsScale = 1.0f;
    }

    public boolean hasNext(int location, OreVeinElementContext context) {
        return this.iterator != null && this.iterator.hasNext();
    }

    public OreVeinElement getNext(int location, OreVeinElementContext context) {
        return this.iterator.next();
    }

    public void end(int location, OreVeinElementContext context) {}
}
