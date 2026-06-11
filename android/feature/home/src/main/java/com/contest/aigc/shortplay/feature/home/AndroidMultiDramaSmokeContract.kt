package com.contest.aigc.shortplay.feature.home

internal val multiDramaHomeSmokeCards = listOf(
    HomeDramaCard(
        dramaId = "tainai3",
        title = "十八岁太奶奶驾到",
        coverUrl = "",
        coverVisual = CoverVisualMetadata(
            style = "family_reversal_poster",
            badge = "高能逆袭",
            hook = "十八岁外表，太奶奶气场回归纪家",
            palette = CoverPalette("#25130F", "#8A4F22", "#F8D36D"),
        ),
        description = "家族逆袭短剧",
        tags = listOf("家族", "逆袭"),
        latestEpisodeNo = 5,
        interactionHint = "已有互动时间线",
        recommendReason = "示例主剧",
        playUrl = "/media/episodes/tainai3_ep01",
        contentSource = "backend",
    ),
    HomeDramaCard(
        dramaId = "new_drama_001",
        title = "新短剧占位",
        coverUrl = "",
        coverVisual = CoverVisualMetadata(
            style = "registry_ingest_poster",
            badge = "新剧接入",
            hook = "等待视频理解生成专属爽点",
            palette = CoverPalette("#182033", "#465A87", "#F2C96D"),
        ),
        description = "通过短剧注册表接入的新内容",
        tags = listOf("新剧"),
        latestEpisodeNo = 1,
        interactionHint = "等待视频理解预热",
        recommendReason = "注册表新增",
        playUrl = "/media/episodes/new_drama_001_ep01",
        contentSource = "backend",
    ),
)

internal val multiDramaCoverVisualSmoke = multiDramaHomeSmokeCards.map { card ->
    "${card.coverVisual.style}:${card.coverVisual.palette.accent}:${card.coverVisual.layers.identityLabel}"
}

internal fun multiDramaStorySummarySmokeStatus(): StorySummaryCacheStatus {
    return fallbackStorySummaryCacheStatus("new_drama_001")
}

internal suspend fun multiDramaOperationsDashboardSmoke(
    repository: ShortPlayRepository,
): OperationsDashboardResult {
    return repository.loadOperationsDashboard(episodeId = "", dramaId = "new_drama_001")
}

internal suspend fun defenseDemoModeSmoke(
    repository: ShortPlayRepository,
): DefenseDemoModeStatus {
    return repository.loadDemoMode(dramaId = "tainai3")
}

internal suspend fun generatedAssetManagementSmoke(
    repository: ShortPlayRepository,
): GeneratedAssetManagementResult {
    return repository.loadGeneratedAssetManagement(dramaId = "tainai3")
}
