package com.quantumgarbage.gtmogs.forge;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.neoforge.event.AddReloadListenerEvent;
import net.neoforged.neoforge.event.RegisterCommandsEvent;
import net.neoforged.neoforge.event.entity.player.PlayerInteractEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.server.ServerStartingEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

import com.quantumgarbage.gtmogs.GTMOGS;
import com.quantumgarbage.gtmogs.api.registry.GTRegistries;
import com.quantumgarbage.gtmogs.common.capability.WorldIDSaveData;
import com.quantumgarbage.gtmogs.common.data.loader.PostRegistryListener;
import com.quantumgarbage.gtmogs.config.ConfigHolder;
import com.quantumgarbage.gtmogs.data.command.GTCommands;
import com.quantumgarbage.gtmogs.data.worldgen.GTOreVeins;
import com.quantumgarbage.gtmogs.integration.map.ClientCacheManager;
import com.quantumgarbage.gtmogs.integration.map.WaypointManager;
import com.quantumgarbage.gtmogs.integration.map.cache.server.ServerCache;
import com.quantumgarbage.gtmogs.utils.TaskHandler;

@EventBusSubscriber(modid = GTMOGS.MOD_ID, bus = EventBusSubscriber.Bus.GAME)
public class CommonEventListener {

    @SubscribeEvent
    public static void registerCommand(RegisterCommandsEvent event) {
        GTCommands.register(event.getDispatcher(), event.getBuildContext());
    }

    // receiveCanceled: prospecting is read-only, so a claim/protection mod
    // canceling the block interaction should not suppress it.
    @SubscribeEvent(receiveCanceled = true)
    public static void onRightClick(PlayerInteractEvent.RightClickBlock event) {
        Level level = event.getLevel();

        if (!level.isClientSide) {
            BlockPos pos = event.getHitVec().getBlockPos();
            Block blockClicked = level.getBlockState(pos).getBlock();
            if (GTOreVeins.getVeinOres().contains(blockClicked)) {
                ServerCache.instance.prospectByOreMaterial(
                        level.dimension(),
                        pos,
                        (ServerPlayer) event.getEntity(), ConfigHolder.INSTANCE.compat.minimap.oreBlockProspectRange);
            }
        }
    }

    @SubscribeEvent
    public static void registerReloadListeners(AddReloadListenerEvent event) {
        GTRegistries.updateFrozenRegistry(event.getRegistryAccess());
        event.addListener(PostRegistryListener.INSTANCE);
    }

    @SubscribeEvent
    public static void levelTick(LevelTickEvent.Post event) {
        if (event.getLevel() instanceof ServerLevel serverLevel) {
            TaskHandler.onTickUpdate(serverLevel);
        }
    }

    @SubscribeEvent
    public static void worldLoad(LevelEvent.Load event) {
        if (event.getLevel().isClientSide()) {
            WaypointManager.updateDimension(event.getLevel());
        } else if (event.getLevel() instanceof ServerLevel serverLevel) {
            ServerCache.instance.maybeInitWorld(serverLevel);
        }
    }

    @SubscribeEvent
    public static void worldUnload(LevelEvent.Unload event) {
        if (event.getLevel() instanceof ServerLevel serverLevel) {
            TaskHandler.onWorldUnLoad(serverLevel);
            ServerCache.instance.invalidateWorld(serverLevel);
        } else if (event.getLevel().isClientSide()) {
            ClientCacheManager.saveCaches(event.getLevel().registryAccess());
        }
    }

    @SubscribeEvent
    public static void serverStarting(ServerStartingEvent event) {
        ServerLevel mainLevel = event.getServer().overworld();
        WorldIDSaveData.init(mainLevel);
    }

    @SubscribeEvent
    public static void serverStopped(ServerStoppedEvent event) {
        ServerCache.instance.clear();
    }
}
