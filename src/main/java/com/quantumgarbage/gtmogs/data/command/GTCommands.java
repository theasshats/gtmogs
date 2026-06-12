package com.quantumgarbage.gtmogs.data.command;

import net.minecraft.commands.CommandBuildContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.ResourceKeyArgument;
import net.minecraft.commands.arguments.coordinates.BlockPosArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.BulkSectionAccess;
import net.minecraft.world.level.levelgen.structure.templatesystem.AlwaysTrueTest;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.brigadier.exceptions.Dynamic2CommandExceptionType;
import com.mojang.brigadier.exceptions.DynamicCommandExceptionType;
import com.quantumgarbage.gtmogs.api.registry.GTRegistries;
import com.quantumgarbage.gtmogs.api.worldgen.OreVeinDefinition;
import com.quantumgarbage.gtmogs.api.worldgen.ores.GeneratedVeinMetadata;
import com.quantumgarbage.gtmogs.api.worldgen.ores.OreGenerator;
import com.quantumgarbage.gtmogs.api.worldgen.ores.OrePlacer;
import com.quantumgarbage.gtmogs.core.mixins.ResourceKeyArgumentAccessor;
import com.quantumgarbage.gtmogs.integration.map.cache.server.ServerCache;

import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static net.minecraft.commands.Commands.*;

public class GTCommands {

    private static final Dynamic2CommandExceptionType VEIN_PLACE_FAILURE = new Dynamic2CommandExceptionType(
            (id, sourcePos) -> Component.translatable("command.gtmogs.place_vein.failure", id, sourcePos));
    private static final DynamicCommandExceptionType ERROR_INVALID_VEIN = new DynamicCommandExceptionType(
            id -> Component.translatableEscape("command.gtmogs.place_vein.invalid", id));

    // spotless:off
    public static void register(CommandDispatcher<CommandSourceStack> dispatcher, CommandBuildContext buildContext) {
        dispatcher.register(literal("gtmogs")
                .then(literal("place_vein")
                        .requires(ctx -> ctx.hasPermission(LEVEL_ADMINS))
                        .then(argument("vein", ResourceKeyArgument.key(GTRegistries.ORE_VEIN_REGISTRY))
                                .executes(context -> {
                                    return GTCommands.placeVein(context, BlockPos.containing(context.getSource().getPosition()));
                                })
                                .then(argument("position", BlockPosArgument.blockPos())
                                        .executes(context -> {
                                            return GTCommands.placeVein(context, BlockPosArgument.getBlockPos(context, "position"));
                                        }))))
                .then(literal("census")
                        .requires(ctx -> ctx.hasPermission(LEVEL_GAMEMASTERS))
                        .executes(GTCommands::veinCensus)));
    }
    // spotless:on

    /**
     * Aggregates the persisted placed-vein records of the source's dimension
     * (the same data prospecting reads) into per-vein counts, so pack
     * calibration does not need to grep debug.log.
     */
    private static int veinCensus(CommandContext<CommandSourceStack> context) {
        ServerLevel level = context.getSource().getLevel();
        String dimension = level.dimension().location().toString();
        List<GeneratedVeinMetadata> veins = ServerCache.instance.getAllVeins(level.dimension());
        if (veins.isEmpty()) {
            context.getSource().sendSuccess(
                    () -> Component.literal("No veins recorded for " + dimension + " yet."), false);
            return 0;
        }

        Map<String, int[]> counts = new HashMap<>();
        for (GeneratedVeinMetadata vein : veins) {
            String id = vein.definition().unwrapKey()
                    .map(key -> key.location().toString())
                    .orElse("(unregistered)");
            int[] tally = counts.computeIfAbsent(id, unused -> new int[2]);
            tally[0]++;
            if (vein.depleted()) tally[1]++;
        }

        StringBuilder report = new StringBuilder("Vein census for " + dimension + ": " +
                veins.size() + " veins, " + counts.size() + " types");
        counts.entrySet().stream()
                .sorted(Comparator.<Map.Entry<String, int[]>>comparingInt(e -> -e.getValue()[0])
                        .thenComparing(Map.Entry::getKey))
                .forEach(e -> {
                    report.append("\n  ").append(e.getKey()).append(": ").append(e.getValue()[0]);
                    if (e.getValue()[1] > 0) {
                        report.append(" (").append(e.getValue()[1]).append(" depleted)");
                    }
                });
        context.getSource().sendSuccess(() -> Component.literal(report.toString()), false);
        return veins.size();
    }

    private static int placeVein(CommandContext<CommandSourceStack> context,
                                 BlockPos sourcePos) throws CommandSyntaxException {
        Holder.Reference<OreVeinDefinition> vein = ResourceKeyArgumentAccessor.callResolveKey(context, "vein",
                GTRegistries.ORE_VEIN_REGISTRY, ERROR_INVALID_VEIN);
        ResourceLocation id = vein.key().location();

        ChunkPos chunkPos = new ChunkPos(sourcePos);
        ServerLevel level = context.getSource().getLevel();

        GeneratedVeinMetadata metadata = new GeneratedVeinMetadata(chunkPos, sourcePos, vein);
        RandomSource random = level.random;

        OrePlacer placer = new OrePlacer();
        OreGenerator generator = placer.getOreGenCache().getOreGenerator();

        try (BulkSectionAccess access = new BulkSectionAccess(level)) {
            var generated = generator.generateOres(new OreGenerator.VeinConfiguration(metadata, random), level,
                    chunkPos);
            if (generated.isEmpty()) {
                throw VEIN_PLACE_FAILURE.create(id.toString(), sourcePos.toString());
            }
            for (ChunkPos pos : generated.get().getGeneratedChunks()) {
                placer.placeVein(pos, random, access, generated.get(), AlwaysTrueTest.INSTANCE);
                level.getChunk(pos.x, pos.z).setUnsaved(true);
            }
            context.getSource().sendSuccess(() -> Component.translatable("command.gtmogs.place_vein.success",
                    id.toString(), sourcePos.toString()), true);
        }

        return 1;
    }
}
