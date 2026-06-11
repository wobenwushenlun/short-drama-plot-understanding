package com.contest.aigc.shortplay.feature.home

import java.util.Locale

data class InteractionComponentProfile(
    val componentType: String,
    val displayName: String,
    val summary: String,
    val usageHint: String,
    val defaultPlacement: String,
    val safeAreaHint: String,
    val aliases: List<String> = emptyList(),
)

object InteractionComponentRegistry {
    fun resolve(
        componentType: String,
        visualStyle: String = "",
        placement: String = "",
    ): InteractionComponentProfile {
        val normalizedType = normalize(componentType)
        val normalizedStyle = visualStyle.trim()
        val resolvedType = when {
            normalizedType.isBlank() -> resolveByStyle(normalizedStyle)
            normalizedType.contains("DANMAKU") -> "DANMAKU_STICKER"
            normalizedType.contains("AIGC") || normalizedType.contains("BOOST") -> "AIGC_CARD"
            normalizedType.contains("SCREEN_TEXT") || normalizedType.contains("EVIDENCE") -> "EVIDENCE_CARD"
            normalizedType.contains("PLOT_EXPECTATION") || normalizedType.contains("SIDE_CHOICE") ||
                normalizedType.contains("CHOICE") -> "CHOICE_CARD"
            normalizedType.contains("REACTION") || normalizedType.contains("STICKER") -> "REACTION_STICKER"
            else -> normalizedType
        }
        val fallbackPlacement = defaultPlacementFor(resolvedType)
        val resolvedPlacement = placement.ifBlank { fallbackPlacement }
        return when (resolvedType) {
            "DANMAKU_STICKER" -> InteractionComponentProfile(
                componentType = resolvedType,
                displayName = "弹幕贴纸",
                summary = "把观众共鸣和跟评集中成轻量贴纸，适合热区、投票和情绪放大。",
                usageHint = "适合高潮、反转和站队点。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
                aliases = listOf("弹幕应援", "弹幕互动"),
            )
            "AIGC_CARD" -> InteractionComponentProfile(
                componentType = resolvedType,
                displayName = "AIGC 卡片",
                summary = "把续写、插片和模型生成结果包装成可读卡片，让能力在播放器里可见。",
                usageHint = "适合反转后、续篇和插片播放。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
                aliases = listOf("生成卡", "续写卡"),
            )
            "EVIDENCE_CARD" -> InteractionComponentProfile(
                componentType = resolvedType,
                displayName = "证据卡",
                summary = "把 ASR、OCR 和关键帧证据转成可解释信息层，便于答辩时直接展示来源。",
                usageHint = "适合证据链、时间线和解释层。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
                aliases = listOf("X-Ray", "证据层"),
            )
            "CHOICE_CARD" -> InteractionComponentProfile(
                componentType = resolvedType,
                displayName = "选择卡",
                summary = "把剧情分支和观众判断变成可点选卡片，承接投票和剧情预判。",
                usageHint = "适合分支选择、预判和站队。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
                aliases = listOf("分支卡", "剧情卡"),
            )
            "REACTION_STICKER" -> InteractionComponentProfile(
                componentType = resolvedType,
                displayName = "反应贴纸",
                summary = "把情绪反馈压缩成一次点击，适合爽点、打脸和快速共鸣。",
                usageHint = "适合高能点、反应点和轻反馈。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
                aliases = listOf("表情贴纸", "反馈贴纸"),
            )
            else -> InteractionComponentProfile(
                componentType = if (resolvedType.isBlank()) "CHOICE_CARD" else resolvedType,
                displayName = normalizedStyle.ifBlank { "互动组件" },
                summary = "统一的可点击互动单元，承接剧情节点和观众反馈。",
                usageHint = "按时间轴和证据链统一渲染。",
                defaultPlacement = resolvedPlacement,
                safeAreaHint = safeAreaHint(resolvedType, resolvedPlacement),
            )
        }
    }

    private fun resolveByStyle(visualStyle: String): String {
        val normalized = visualStyle.trim()
        return when {
            normalized.contains("弹幕") -> "DANMAKU_STICKER"
            normalized.contains("加速") -> "AIGC_CARD"
            normalized.contains("证据") || normalized.contains("复盘") || normalized.contains("身价") -> "EVIDENCE_CARD"
            normalized.contains("选择") || normalized.contains("预判") -> "CHOICE_CARD"
            normalized.contains("表情") || normalized.contains("贴纸") -> "REACTION_STICKER"
            else -> "CHOICE_CARD"
        }
    }

    private fun defaultPlacementFor(componentType: String): String {
        return when (componentType) {
            "DANMAKU_STICKER" -> "TOP_CENTER"
            "REACTION_STICKER" -> "CENTER_END"
            "AIGC_CARD" -> "CENTER"
            "EVIDENCE_CARD" -> "CENTER_START"
            else -> "BOTTOM_CENTER"
        }
    }

    private fun safeAreaHint(componentType: String, placement: String): String {
        return when {
            componentType == "DANMAKU_STICKER" -> "顶部避让标题和弹幕层"
            placement.startsWith("TOP") -> "顶部避让标题区"
            placement.endsWith("END") -> "靠右展示，避让操作栏"
            componentType == "AIGC_CARD" -> "居中展示，保留播放器可视区域"
            componentType == "EVIDENCE_CARD" -> "保留证据阅读空间，避让底部控件"
            else -> "自动避让进度条和手势区"
        }
    }

    private fun normalize(value: String): String {
        return value.trim().uppercase(Locale.ROOT)
    }
}

fun InteractionNode.componentProfile(): InteractionComponentProfile {
    return InteractionComponentRegistry.resolve(
        componentType = componentType,
        visualStyle = visualStyle,
        placement = placement,
    )
}

fun InteractionTimedEvent.componentProfile(): InteractionComponentProfile {
    return InteractionComponentRegistry.resolve(
        componentType = componentType,
        visualStyle = visualStyle,
        placement = placement,
    )
}
