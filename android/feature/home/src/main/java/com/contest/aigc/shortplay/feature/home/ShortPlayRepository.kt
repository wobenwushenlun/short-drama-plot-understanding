package com.contest.aigc.shortplay.feature.home

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private const val DEFAULT_BACKEND_BASE_URL = "https://api.xdyygl.top"
private const val FAST_CONTENT_TIMEOUT_MS = 5_000
private const val DEFAULT_CONTENT_TIMEOUT_MS = 20_000
private const val AIGC_GENERATION_TIMEOUT_MS = 180_000

interface ShortPlayRepository {
    suspend fun loadHome(): List<HomeDramaCard>
    suspend fun loadHomeHighlightFeed(
        size: Int = 6,
        strategy: String = "heat_score_desc_v1",
    ): List<ShareableMoment>
    suspend fun loadDemoRoute(dramaId: String = "tainai3"): DemoRoutePlan
    suspend fun loadDemoMode(dramaId: String = "tainai3"): DefenseDemoModeStatus
    suspend fun loadDrama(dramaId: String): DramaDetailModel
    suspend fun loadEpisodes(dramaId: String): List<EpisodeCard>
    suspend fun loadStorySummaryCacheStatus(dramaId: String = "tainai3"): StorySummaryCacheStatus
    suspend fun refreshStorySummaryCache(dramaId: String = "tainai3"): StorySummaryCacheStatus
    suspend fun loadShareableMoments(dramaId: String = "tainai3"): List<ShareableMoment>
    suspend fun loadSavedMoments(dramaId: String = "tainai3"): List<ShareableMoment>
    suspend fun saveShareableMoment(moment: ShareableMoment): ShareableMoment
    suspend fun loadPlayEpisode(episodeId: String): PlaybackEpisode
    suspend fun loadInteractionConfig(episodeId: String): InteractionConfig
    suspend fun loadInteractionCandidates(episodeId: String): List<InteractionCandidateNode>
    suspend fun loadDanmakuEmotionReport(episodeId: String): DanmakuEmotionReport
    suspend fun reviewInteractionCandidate(
        episodeId: String,
        candidateId: String,
        reviewStatus: String,
        editedQuestion: String = "",
        editedOptions: List<String> = emptyList(),
        reviewNote: String = "",
    ): InteractionCandidateReviewResult
    suspend fun loadInteractionInsights(episodeId: String): InteractionInsights
    suspend fun loadWatchHistory(size: Int = 20): List<WatchHistoryItem>
    suspend fun loadAiContentRecap(episodeId: String, dramaId: String = "tainai3"): AiContentRecapResult
    suspend fun loadAiInteractionFeedback(
        episodeId: String,
        nodeId: String,
        optionId: String,
        answerText: String = "",
        sceneSummary: String = "",
        dramaId: String = "tainai3",
    ): AiInteractionFeedbackResult
    suspend fun loadAiTagExtract(
        episodeId: String,
        nodeId: String = "",
        optionId: String = "",
        answerText: String = "",
        sceneSummary: String = "",
        dramaId: String = "tainai3",
    ): AiTagExtractResult
    suspend fun loadAiModerationCheck(text: String): AiModerationResult
    suspend fun loadAiDiscussionSeed(
        episodeId: String,
        nodeId: String,
        optionId: String,
        selectionText: String = "",
        dramaId: String = "tainai3",
    ): AiDiscussionSeedResult
    suspend fun loadAiStoryContinuation(
        episodeId: String,
        dramaId: String = "tainai3",
        userIntent: String = "",
        desiredEnding: String = "",
        visualDirection: String = "",
    ): AiStoryContinuationResult
    suspend fun loadAgnesStatus(): AgnesStatusResult
    suspend fun loadAiCheckinCard(
        episodeId: String,
        dramaId: String = "tainai3",
        momentId: String = "",
        style: String = "short_drama_poster",
        userIntent: String = "",
        desiredEnding: String = "",
        visualDirection: String = "",
    ): AiCheckinCardResult
    suspend fun createGenerationTask(
        taskType: String,
        episodeId: String,
        dramaId: String = "tainai3",
        momentId: String = "",
        style: String = "",
    ): GenerationTaskResult
    suspend fun loadGenerationTask(taskId: String): GenerationTaskResult
    suspend fun loadGeneratedAssetManagement(dramaId: String = "tainai3"): GeneratedAssetManagementResult
    suspend fun cleanupFailedGeneratedAssets(dramaId: String = "tainai3"): GeneratedAssetCleanupResult
    suspend fun loadAiHistoryRecap(size: Int = 5, dramaId: String = ""): AiHistoryRecapResult
    suspend fun loadAiHomeRecommend(size: Int = 5, dramaId: String = ""): AiHomeRecommendResult
    suspend fun loadOperationsDashboard(episodeId: String = "", dramaId: String = ""): OperationsDashboardResult
    suspend fun loadQualityEvaluation(): QualityEvaluationResult
    suspend fun loadAiVideoUnderstanding(
        episodeId: String,
        dramaId: String = "tainai3",
        includeFrames: Boolean = true,
    ): AiVideoUnderstandingResult
    suspend fun reportWatchProgress(
        dramaId: String,
        episodeId: String,
        progressMs: Long,
        durationMs: Long,
        isCompleted: Boolean,
    )
    suspend fun reportTelemetryEvents(events: List<TelemetryEvent>): TelemetryDispatchResult
    suspend fun submitInteraction(
        dramaId: String,
        episodeId: String,
        node: InteractionNode,
        option: InteractionOption,
    ): InteractionSubmitResult
}

class BackendShortPlayRepository(
    private val baseUrl: String = DEFAULT_BACKEND_BASE_URL,
) : ShortPlayRepository {
    private val normalizedBaseUrl = baseUrl.trimEnd('/')

    override suspend fun loadHome(): List<HomeDramaCard> {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson("/home/recommend", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
                    val items = root.getJSONObject("data").getJSONArray("items")
                    items.toHomeCards(normalizedBaseUrl)
                },
                fallback = { fallbackHomeCards(normalizedBaseUrl) },
            )
        }
    }

    override suspend fun loadHomeHighlightFeed(size: Int, strategy: String): List<ShareableMoment> {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson(
                        "/home/highlight-feed?size=$size&strategy=$strategy",
                        readTimeoutMs = FAST_CONTENT_TIMEOUT_MS
                    )
                    root.getJSONObject("data").getJSONArray("items").toShareableMoments()
                },
                fallback = { emptyList() },
            )
        }
    }

    override suspend fun loadDemoRoute(dramaId: String): DemoRoutePlan {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson(
                        "/demo/route?drama_id=$dramaId",
                        readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
                    )
                    root.getJSONObject("data").toDemoRoutePlan()
                },
                fallback = { fallbackDemoRoute(dramaId) },
            )
        }
    }

    override suspend fun loadDemoMode(dramaId: String): DefenseDemoModeStatus {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson(
                        "/demo/mode?drama_id=$dramaId",
                        readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
                    )
                    root.getJSONObject("data").toDefenseDemoModeStatus()
                },
                fallback = { fallbackDefenseDemoMode(dramaId) },
            )
        }
    }

    override suspend fun loadDrama(dramaId: String): DramaDetailModel {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson("/dramas/$dramaId", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
                    root.getJSONObject("data").toDramaDetail()
                },
                fallback = { fallbackDramaDetail(dramaId) },
            )
        }
    }

    override suspend fun loadEpisodes(dramaId: String): List<EpisodeCard> {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson("/dramas/$dramaId/episodes", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
                    val episodes = root.getJSONObject("data").getJSONArray("episodes")
                    episodes.toEpisodeCards(normalizedBaseUrl)
                },
                fallback = { fallbackEpisodeCards(normalizedBaseUrl, dramaId) },
            )
        }
    }

    override suspend fun loadStorySummaryCacheStatus(dramaId: String): StorySummaryCacheStatus {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson("/story-summary/cache?drama_id=$dramaId", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
                    root.getJSONObject("data").toStorySummaryCacheStatus()
                },
                fallback = { fallbackStorySummaryCacheStatus(dramaId) },
            )
        }
    }

    override suspend fun refreshStorySummaryCache(dramaId: String): StorySummaryCacheStatus {
        return withContext(Dispatchers.IO) {
            val root = requestJson(
                path = "/story-summary/cache/refresh",
                method = "POST",
                body = JSONObject().put("dramaId", dramaId),
                readTimeoutMs = DEFAULT_CONTENT_TIMEOUT_MS,
            )
            root.getJSONObject("data").toStorySummaryCacheStatus()
        }
    }

    override suspend fun loadShareableMoments(dramaId: String): List<ShareableMoment> {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/dramas/$dramaId/shareable-moments", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").getJSONArray("items").toShareableMoments()
        }
    }

    override suspend fun loadSavedMoments(dramaId: String): List<ShareableMoment> {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/moments/saved?drama_id=$dramaId", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").getJSONArray("items").toShareableMoments()
        }
    }

    override suspend fun saveShareableMoment(moment: ShareableMoment): ShareableMoment {
        return withContext(Dispatchers.IO) {
            val root = requestJson(
                path = "/moments/save",
                method = "POST",
                body = moment.toJsonObject().put("clientTsMs", System.currentTimeMillis()),
                readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
            )
            root.getJSONObject("data").toShareableMoment()
        }
    }

    override suspend fun loadPlayEpisode(episodeId: String): PlaybackEpisode {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/episodes/$episodeId/play")
            root.getJSONObject("data").toPlaybackEpisode()
        }
    }

    override suspend fun loadInteractionConfig(episodeId: String): InteractionConfig {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/episodes/$episodeId/timed-events")
            root.getJSONObject("data").toInteractionConfig()
        }
    }

    override suspend fun loadInteractionCandidates(episodeId: String): List<InteractionCandidateNode> {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/episodes/$episodeId/interaction-candidates", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").getJSONArray("items").toInteractionCandidateNodes()
        }
    }

    override suspend fun loadDanmakuEmotionReport(episodeId: String): DanmakuEmotionReport {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/episodes/$episodeId/danmaku-emotion-report", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").toDanmakuEmotionReport()
        }
    }

    override suspend fun reviewInteractionCandidate(
        episodeId: String,
        candidateId: String,
        reviewStatus: String,
        editedQuestion: String,
        editedOptions: List<String>,
        reviewNote: String,
    ): InteractionCandidateReviewResult {
        return withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("episodeId", episodeId)
                .put("reviewStatus", reviewStatus)
                .put("editedQuestion", editedQuestion)
                .put("editedOptions", JSONArray(editedOptions))
                .put("reviewNote", reviewNote)
            val root = requestJson(
                path = "/interaction-candidates/$candidateId/review",
                method = "POST",
                body = body,
                readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
            )
            root.getJSONObject("data").toInteractionCandidateReviewResult()
        }
    }

    override suspend fun loadInteractionInsights(episodeId: String): InteractionInsights {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/episodes/$episodeId/interaction-insights")
            root.getJSONObject("data").toInteractionInsights()
        }
    }

    override suspend fun loadWatchHistory(size: Int): List<WatchHistoryItem> {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/user/history?size=$size")
            val items = root.getJSONObject("data").getJSONArray("items")
            items.toWatchHistoryItems(normalizedBaseUrl)
        }
    }

    override suspend fun loadAiContentRecap(episodeId: String, dramaId: String): AiContentRecapResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("includeDiscussionSeeds", true)
                .put("locale", "zh-CN")
            val root = requestJson("/ai/content/recap", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiContentRecapResult()
        }
    }

    override suspend fun loadAiInteractionFeedback(
        episodeId: String,
        nodeId: String,
        optionId: String,
        answerText: String,
        sceneSummary: String,
        dramaId: String,
    ): AiInteractionFeedbackResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("nodeId", nodeId)
                .put("optionId", optionId)
                .put("answerText", answerText)
                .put("sceneSummary", sceneSummary)
            val root = requestJson("/ai/interaction/feedback", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiInteractionFeedbackResult()
        }
    }

    override suspend fun loadAiTagExtract(
        episodeId: String,
        nodeId: String,
        optionId: String,
        answerText: String,
        sceneSummary: String,
        dramaId: String,
    ): AiTagExtractResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("nodeId", nodeId)
                .put("optionId", optionId)
                .put("answerText", answerText)
                .put("sceneSummary", sceneSummary)
            val root = requestJson("/ai/tag/extract", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiTagExtractResult()
        }
    }

    override suspend fun loadAiModerationCheck(text: String): AiModerationResult {
        return withContext(Dispatchers.IO) {
            val root = requestJson(
                path = "/ai/moderation/check",
                method = "POST",
                body = JSONObject().put("text", text),
            )
            root.getJSONObject("data").toAiModerationResult()
        }
    }

    override suspend fun loadAiDiscussionSeed(
        episodeId: String,
        nodeId: String,
        optionId: String,
        selectionText: String,
        dramaId: String,
    ): AiDiscussionSeedResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("nodeId", nodeId)
                .put("optionId", optionId)
                .put("selectionText", selectionText)
            val root = requestJson("/ai/discussion/seed", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiDiscussionSeedResult()
        }
    }

    override suspend fun loadAiStoryContinuation(
        episodeId: String,
        dramaId: String,
        userIntent: String,
        desiredEnding: String,
        visualDirection: String,
    ): AiStoryContinuationResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("userIntent", userIntent)
                .put("desiredEnding", desiredEnding)
                .put("visualDirection", visualDirection)
            val root = requestJson(
                "/ai/story/continuation",
                method = "POST",
                body = requestBody,
                readTimeoutMs = AIGC_GENERATION_TIMEOUT_MS,
            )
            root.getJSONObject("data").toAiStoryContinuationResult()
        }
    }

    override suspend fun loadAgnesStatus(): AgnesStatusResult {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/ai/agnes/status", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").toAgnesStatusResult()
        }
    }

    override suspend fun loadAiCheckinCard(
        episodeId: String,
        dramaId: String,
        momentId: String,
        style: String,
        userIntent: String,
        desiredEnding: String,
        visualDirection: String,
    ): AiCheckinCardResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("momentId", momentId)
                .put("style", style)
                .put("userIntent", userIntent)
                .put("desiredEnding", desiredEnding)
                .put("visualDirection", visualDirection)
            val root = requestJson(
                "/ai/checkin-card",
                method = "POST",
                body = requestBody,
                readTimeoutMs = AIGC_GENERATION_TIMEOUT_MS,
            )
            root.getJSONObject("data").toAiCheckinCardResult()
        }
    }

    override suspend fun createGenerationTask(
        taskType: String,
        episodeId: String,
        dramaId: String,
        momentId: String,
        style: String,
    ): GenerationTaskResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("taskType", taskType)
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("momentId", momentId)
                .put("style", style)
            val root = requestJson(
                "/ai/generation/tasks",
                method = "POST",
                body = requestBody,
                readTimeoutMs = AIGC_GENERATION_TIMEOUT_MS,
            )
            root.getJSONObject("data").toGenerationTaskResult()
        }
    }

    override suspend fun loadGenerationTask(taskId: String): GenerationTaskResult {
        return withContext(Dispatchers.IO) {
            val root = requestJson(
                "/ai/generation/tasks/$taskId",
                readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
            )
            root.getJSONObject("data").toGenerationTaskResult()
        }
    }

    override suspend fun loadGeneratedAssetManagement(dramaId: String): GeneratedAssetManagementResult {
        return withContext(Dispatchers.IO) {
            fallbackOnFailure(
                block = {
                    val root = requestJson(
                        "/ai/generated-assets?drama_id=$dramaId",
                        readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
                    )
                    root.getJSONObject("data").toGeneratedAssetManagementResult()
                },
                fallback = { fallbackGeneratedAssetManagement(dramaId) },
            )
        }
    }

    override suspend fun cleanupFailedGeneratedAssets(dramaId: String): GeneratedAssetCleanupResult {
        return withContext(Dispatchers.IO) {
            val root = requestJson(
                "/ai/generated-assets/failed?drama_id=$dramaId",
                method = "DELETE",
                readTimeoutMs = FAST_CONTENT_TIMEOUT_MS,
            )
            root.getJSONObject("data").toGeneratedAssetCleanupResult()
        }
    }

    override suspend fun loadAiHistoryRecap(size: Int, dramaId: String): AiHistoryRecapResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("size", size)
                .put("dramaId", dramaId)
            val root = requestJson("/ai/history/recap", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiHistoryRecapResult()
        }
    }

    override suspend fun loadAiHomeRecommend(size: Int, dramaId: String): AiHomeRecommendResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("size", size)
                .put("dramaId", dramaId)
            val root = requestJson("/ai/recommend/home", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiHomeRecommendResult()
        }
    }

    override suspend fun loadOperationsDashboard(episodeId: String, dramaId: String): OperationsDashboardResult {
        return withContext(Dispatchers.IO) {
            val queryParts = mutableListOf<String>()
            if (episodeId.isNotBlank()) {
                queryParts += "episode_id=$episodeId"
            }
            if (dramaId.isNotBlank()) {
                queryParts += "drama_id=$dramaId"
            }
            val path = if (queryParts.isEmpty()) "/dashboard/operations" else "/dashboard/operations?${queryParts.joinToString("&")}"
            val root = requestJson(path, readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").toOperationsDashboardResult()
        }
    }

    override suspend fun loadQualityEvaluation(): QualityEvaluationResult {
        return withContext(Dispatchers.IO) {
            val root = requestJson("/quality/evaluation", readTimeoutMs = FAST_CONTENT_TIMEOUT_MS)
            root.getJSONObject("data").toQualityEvaluationResult()
        }
    }

    override suspend fun loadAiVideoUnderstanding(
        episodeId: String,
        dramaId: String,
        includeFrames: Boolean,
    ): AiVideoUnderstandingResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("episodeId", episodeId)
                .put("dramaId", dramaId)
                .put("includeFrames", includeFrames)
                .put("maxFrames", 3)
            val root = requestJson("/ai/video/analyze", method = "POST", body = requestBody)
            root.getJSONObject("data").toAiVideoUnderstandingResult()
        }
    }

    override suspend fun reportWatchProgress(
        dramaId: String,
        episodeId: String,
        progressMs: Long,
        durationMs: Long,
        isCompleted: Boolean,
    ) {
        withContext(Dispatchers.IO) {
            requestJson(
                path = "/watch/progress",
                method = "POST",
                body = JSONObject()
                    .put("dramaId", dramaId)
                    .put("episodeId", episodeId)
                    .put("progressMs", progressMs)
                    .put("durationMs", durationMs)
                    .put("isCompleted", isCompleted)
                    .put("clientTsMs", System.currentTimeMillis()),
            )
        }
    }

    override suspend fun reportTelemetryEvents(events: List<TelemetryEvent>): TelemetryDispatchResult {
        return withContext(Dispatchers.IO) {
            val eventArray = JSONArray()
            events.forEach { event ->
                eventArray.put(
                    JSONObject()
                        .put("eventId", event.eventId)
                        .put("eventName", event.eventName)
                        .put("screenName", event.screenName)
                        .put("dramaId", event.dramaId)
                        .put("episodeId", event.episodeId)
                        .put("nodeId", event.nodeId)
                        .put("progressMs", event.progressMs)
                        .put("clientTsMs", event.clientTsMs)
                        .put("properties", JSONObject(event.properties))
                )
            }
            val root = requestJson(
                path = "/analytics/events",
                method = "POST",
                body = JSONObject().put("events", eventArray),
            )
            root.getJSONObject("data").toTelemetryDispatchResult()
        }
    }

    override suspend fun submitInteraction(
        dramaId: String,
        episodeId: String,
        node: InteractionNode,
        option: InteractionOption,
    ): InteractionSubmitResult {
        return withContext(Dispatchers.IO) {
            val requestBody = JSONObject()
                .put("submitId", UUID.randomUUID().toString())
                .put("dramaId", dramaId)
                .put("episodeId", episodeId)
                .put("nodeId", node.id)
                .put("triggerMs", node.triggerMs)
                .put("answer", JSONObject().put("optionId", option.id))
                .put("clientTsMs", System.currentTimeMillis())

            val root = requestJson(
                path = "/interaction/submit",
                method = "POST",
                body = requestBody,
            )
            root.getJSONObject("data").toInteractionSubmitResult()
        }
    }

    private fun requestJson(
        path: String,
        method: String = "GET",
        body: JSONObject? = null,
        readTimeoutMs: Int = DEFAULT_CONTENT_TIMEOUT_MS,
    ): JSONObject {
        val url = URL("$normalizedBaseUrl$path")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 8_000
            readTimeout = readTimeoutMs
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }

        if (body != null) {
            connection.outputStream.writer(Charsets.UTF_8).use { writer ->
                writer.write(body.toString())
            }
        }

        return try {
            val status = connection.responseCode
            val responseBody = if (status in 200..299) {
                connection.inputStream.bufferedReader().use { it.readText() }
            } else {
                connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
            }
            if (status !in 200..299) {
                throw IOException("HTTP $status for $path${if (responseBody.isBlank()) "" else ": $responseBody"}")
            }
            JSONObject(responseBody)
        } finally {
            connection.disconnect()
        }
    }
}

private inline fun <T> fallbackOnFailure(block: () -> T, fallback: () -> T): T {
    return try {
        block()
    } catch (error: CancellationException) {
        throw error
    } catch (_: Throwable) {
        fallback()
    }
}

private fun fallbackHomeCards(baseUrl: String): List<HomeDramaCard> {
    return listOf(
        HomeDramaCard(
            dramaId = "tainai3",
            title = "十八岁太奶奶驾到，重整家族荣耀第三部",
            coverUrl = "",
            coverVisual = CoverVisualMetadata(
                style = "family_reversal_poster",
                badge = "高能逆袭",
                hook = "十八岁外表，太奶奶气场回归纪家",
                palette = CoverPalette("#25130F", "#8A4F22", "#F8D36D"),
            ),
            description = FALLBACK_DRAMA_DESCRIPTION,
            tags = listOf("家族", "逆袭", "短剧"),
            latestEpisodeNo = 5,
            interactionHint = "后端不可用时显示本地剧情兜底",
            recommendReason = "基于观看和互动行为推荐",
            playUrl = "$baseUrl/media/episodes/tainai3_ep01",
            contentSource = "local_fallback",
        )
    )
}

private fun fallbackDramaDetail(dramaId: String): DramaDetailModel {
    if (dramaId != "tainai3") {
        throw IOException("drama not found: $dramaId")
    }
    return DramaDetailModel(
        dramaId = "tainai3",
        title = "十八岁太奶奶驾到，重整家族荣耀第三部",
        coverUrl = "",
        coverVisual = CoverVisualMetadata(
            style = "family_reversal_poster",
            badge = "高能逆袭",
            hook = "十八岁外表，太奶奶气场回归纪家",
            palette = CoverPalette("#25130F", "#8A4F22", "#F8D36D"),
        ),
        description = FALLBACK_DRAMA_DESCRIPTION,
        tags = listOf("家族", "逆袭", "短剧"),
        characters = listOf(
            DramaCharacter(
                characterId = "char_grandma",
                name = "太奶奶",
                avatarUrl = "",
            ),
            DramaCharacter(
                characterId = "char_grandson",
                name = "家族少爷",
                avatarUrl = "",
            ),
        ),
        latestEpisodeNo = 5,
        interactionHint = "后端不可用时显示本地剧情兜底",
    )
}

private fun fallbackEpisodeCards(baseUrl: String, dramaId: String): List<EpisodeCard> {
    if (dramaId != "tainai3") {
        throw IOException("drama not found: $dramaId")
    }
    return FALLBACK_EPISODE_SUMMARIES.mapIndexed { index, summary ->
        val episodeNo = index + 1
        EpisodeCard(
            episodeId = "tainai3_ep%02d".format(episodeNo),
            episodeNo = episodeNo,
            title = "第${episodeNo}集",
            durationMs = FALLBACK_EPISODE_DURATIONS_MS.getOrElse(index) { 0L },
            summary = summary,
            playUrl = "$baseUrl/media/episodes/tainai3_ep%02d".format(episodeNo),
        )
    }
}

internal fun fallbackStorySummaryCacheStatus(dramaId: String): StorySummaryCacheStatus {
    return StorySummaryCacheStatus(
        dramaId = dramaId,
        promptVersion = "pending_video_understanding",
        source = "local_fallback",
        status = "pending_ingest",
        generatedAtMs = 0L,
        modelName = "",
        latencyMs = 0L,
        degradeReason = "story summary cache is not ready for this drama",
        dramaDescription = "该短剧已接入内容目录，等待视频理解预热生成整剧剧情简介。",
        episodes = emptyList(),
        latestAttempt = StorySummaryCacheAttempt(
            source = "local_fallback",
            status = "pending_ingest",
            generatedAtMs = 0L,
            modelName = "",
            latencyMs = 0L,
            degradeReason = "story summary cache is not ready for this drama",
        ),
    )
}

private fun fallbackDemoRoute(dramaId: String): DemoRoutePlan {
    if (dramaId != "tainai3") {
        throw IOException("demo route not found: $dramaId")
    }
    return DemoRoutePlan(
        routeId = "tainai3_defense_demo_v1",
        dramaId = "tainai3",
        title = "推荐答辩演示路线",
        source = "local_fallback",
        entry = DemoRouteEntry(
            episodeId = "tainai3_ep01",
            startMs = 36_000L,
            momentId = "local_demo_highlight",
            title = "太奶奶登场高能",
        ),
        steps = listOf(
            DemoRouteStep("home_highlight_feed", 1, "首页高能流", "后端不可用时使用本地高能入口兜底。", "open_home", "/home/highlight-feed", "local_fallback", "tainai3_ep01", 36_000L, 0),
            DemoRouteStep("player_highlight", 2, "播放高光点", "从高光点进入播放器。", "open_episode", "/episodes/tainai3_ep01/play", "local_fallback", "tainai3_ep01", 36_000L, 0),
            DemoRouteStep("xray_evidence", 3, "X-Ray 证据解释", "后端恢复后展示证据图谱。", "open_xray", "/episodes/tainai3_ep01/evidence-graph", "degraded", "tainai3_ep01", 44_000L, 0),
            DemoRouteStep("interaction_click", 4, "互动点击", "点击后进入 SQLite 统计。", "submit_interaction", "/interactions/submit", "local_fallback", "tainai3_ep01", 44_000L, 0),
            DemoRouteStep("aigc_generation", 5, "Agnes 续写/打卡", "进入 AI 体验页触发生成任务。", "open_ai_generation_task", "/ai/generation/tasks", "local_fallback", "tainai3_ep01", 44_000L, 0),
            DemoRouteStep("operations_dashboard", 6, "运营看板", "后端恢复后查看 SQLite 指标。", "open_operations_dashboard", "/dashboard/operations", "local_fallback", "tainai3_ep01", 44_000L, 0),
        ),
        checks = DemoRouteChecks(
            usesFakeData = false,
            restartSafe = true,
            homeFallbackAvailable = true,
            sqliteBacked = true,
            evidenceGraphAvailable = false,
        ),
    )
}

private fun fallbackDefenseDemoMode(dramaId: String): DefenseDemoModeStatus {
    val route = fallbackDemoRoute(dramaId)
    return DefenseDemoModeStatus(
        enabled = true,
        routeId = route.routeId,
        dramaId = route.dramaId,
        title = "答辩演示模式",
        description = "固定首页高能流、播放高光点、X-Ray、互动、AIGC 和运营看板链路。",
        fixedStrategy = "heat_score_desc_v1",
        contentSource = "local_fallback",
        entry = route.entry,
        quickSteps = route.steps.map { step ->
            DefenseDemoQuickStep(
                stepId = step.stepId,
                title = step.title,
                actionType = step.actionType,
                status = step.status,
                api = step.api,
            )
        },
        fallbacks = DefenseDemoFallbacks(
            homeFallbackAvailable = route.checks.homeFallbackAvailable,
            sqliteBacked = route.checks.sqliteBacked,
            evidenceGraphAvailable = route.checks.evidenceGraphAvailable,
            lastSuccessArtifactAvailable = false,
        ),
    )
}

private fun fallbackGeneratedAssetManagement(dramaId: String): GeneratedAssetManagementResult {
    return GeneratedAssetManagementResult(
        dramaId = dramaId,
        summary = GeneratedAssetManagementSummary(
            successCount = 0,
            failedCount = 0,
            cachedByteSize = 0L,
            source = "local_fallback",
        ),
        recentSuccesses = emptyList(),
        failedAttempts = emptyList(),
    )
}

private val FALLBACK_EPISODE_DURATIONS_MS = listOf(
    245_840L,
    275_000L,
    254_440L,
    174_320L,
    133_000L,
)

private const val FALLBACK_DRAMA_DESCRIPTION =
    "1955年，容遇教授意外去世后醒来，竟穿到七十年后一位同名同姓的十八岁少女身上。" +
        "昔日儿子已成纪家掌权人，她却被当成来路不明的闯入者。面对晚辈误会、家族内斗和外部危机，" +
        "容遇一边隐藏穿越真相，一边用智慧与气场重新掌控纪家，把濒临失控的家族带回荣耀巅峰。"

private val FALLBACK_EPISODE_SUMMARIES = listOf(
    "第1集｜1955年容遇教授意外身故，一睁眼却成了七十年后的十八岁少女。她被带到纪家后遭到质疑，只能先稳住局面，寻找自己与这个家族的真实联系。",
    "第2集｜纪家众人不相信眼前少女与太奶奶有关，试探和嘲讽不断升级。容遇没有正面摊牌，而是用判断力和气场让局面开始反转。",
    "第3集｜围绕容遇身份的线索继续浮出水面，纪家人的态度出现动摇。她在误解与逼问中抓住主动权，也让家族旧事露出新的破口。",
    "第4集｜冲突从口头质疑升级为正面对线，容遇的手腕逐渐压住场面。纪家内部压力被推到台前，新的反转也被推向临界点。",
    "第5集｜前几集埋下的人物关系和身份线索开始汇合，容遇在关键抉择前稳住局势。家族成员立场逐渐分化，更大的危机与打脸时刻即将到来。",
)

private fun JSONArray.toHomeCards(baseUrl: String): List<HomeDramaCard> {
    val result = mutableListOf<HomeDramaCard>()
    for (index in 0 until length()) {
        result += getJSONObject(index).toHomeCard(baseUrl)
    }
    return result
}

private fun JSONObject.toHomeCard(baseUrl: String): HomeDramaCard {
    return HomeDramaCard(
        dramaId = getString("drama_id"),
        title = getString("title"),
        coverUrl = optString("cover_url"),
        coverVisual = toCoverVisualMetadata(),
        description = optString("description"),
        tags = optStringArray("tags"),
        latestEpisodeNo = optInt("latest_episode_no"),
        interactionHint = optString("interaction_hint"),
        recommendReason = optString("recommend_reason", "基于观看和互动行为推荐"),
        playUrl = optString("play_url", "$baseUrl/media/episodes/tainai3_ep01"),
        contentSource = optString("content_source", "backend"),
    )
}

private fun JSONObject.toDramaDetail(): DramaDetailModel {
    return DramaDetailModel(
        dramaId = getString("drama_id"),
        title = getString("title"),
        coverUrl = optString("cover_url"),
        coverVisual = toCoverVisualMetadata(),
        description = optString("description"),
        tags = optStringArray("tags"),
        characters = optJSONArray("characters").toDramaCharacters(),
        latestEpisodeNo = optInt("latest_episode_no"),
        interactionHint = optString("interaction_hint"),
    )
}

private fun JSONObject.toCoverVisualMetadata(): CoverVisualMetadata {
    return CoverVisualMetadata(
        style = optString("cover_style", optString("coverStyle", "family_reversal_poster")),
        badge = optString("cover_badge", optString("coverBadge", "高能逆袭")),
        hook = optString("cover_hook", optString("coverHook", "十八岁外表，太奶奶气场回归纪家")),
        palette = (optJSONObject("cover_palette") ?: optJSONObject("coverPalette")).toCoverPalette(),
        layers = (optJSONObject("cover_layers") ?: optJSONObject("coverLayers")).toCoverVisualLayers(),
    )
}

private fun JSONObject?.toCoverPalette(): CoverPalette {
    if (this == null) {
        return CoverPalette()
    }
    return CoverPalette(
        primary = optString("primary", "#25130F"),
        secondary = optString("secondary", "#8A4F22"),
        accent = optString("accent", "#F8D36D"),
    )
}

private fun JSONObject?.toCoverVisualLayers(): CoverVisualLayers {
    if (this == null) {
        return CoverVisualLayers()
    }
    return CoverVisualLayers(
        portraitUrl = optString("portrait_url", optString("portraitUrl", "")),
        identityLabel = optString("identity_label", optString("identityLabel", "身份反转")),
        heatLabel = optString("heat_label", optString("heatLabel", "178.8万人想看")),
        latestLabel = optString("latest_label", optString("latestLabel", "")),
        shareHint = optString("share_hint", optString("shareHint", "生成同款打卡图")),
    )
}

private fun JSONObject.toPlaybackEpisode(): PlaybackEpisode {
    val episodeId = getString("episode_id")
    val episodeNo = optInt("episode_no", 0)
    return PlaybackEpisode(
        episodeId = episodeId,
        title = resolvePlaybackEpisodeTitle(optString("title"), episodeNo, episodeId),
        playUrl = getString("play_url"),
        hlsUrl = optString("hls_url"),
        hlsAvailable = optBoolean("hls_available", false),
        preferredPlayUrl = optString("preferred_play_url").ifBlank { getString("play_url") },
        expireAtMs = optLong("expire_at_ms"),
    )
}

private fun resolvePlaybackEpisodeTitle(rawTitle: String, episodeNo: Int, episodeId: String): String {
    if (rawTitle.isNotBlank()) {
        return rawTitle
    }
    if (episodeNo > 0) {
        return "第${episodeNo}集"
    }
    val parsedNo = Regex("""ep0*(\d+)""", RegexOption.IGNORE_CASE).find(episodeId)
        ?.groupValues
        ?.getOrNull(1)
        ?.toIntOrNull()
    return if (parsedNo != null && parsedNo > 0) {
        "第${parsedNo}集"
    } else {
        "未命名剧集"
    }
}

private fun JSONObject.toInteractionConfig(): InteractionConfig {
    val drama = getJSONObject("drama")
    val episode = getJSONObject("episode")
    val timelineItems = optJSONArray("timeline_items").toInteractionTimelineItems()
    val nodes = optJSONArray("timeline_items").toInteractionNodesFromTimeline()
        .takeIf { it.isNotEmpty() }
        ?: getJSONArray("nodes").toInteractionNodes()
    return InteractionConfig(
        dramaId = drama.getString("dramaId"),
        episodeId = episode.getString("episodeId"),
        nodes = nodes,
        timelineItems = timelineItems,
        timedEvents = optJSONArray("events").toInteractionTimedEvents(),
        generationPipeline = optJSONObject("generationPipeline").toInteractionGenerationPipeline(),
        evidenceGraph = optJSONObject("evidenceGraph").toEvidenceGraph(),
    )
}

private fun JSONObject?.toInteractionGenerationPipeline(): InteractionGenerationPipeline? {
    if (this == null) {
        return null
    }
    return InteractionGenerationPipeline(
        mode = optString("mode"),
        sourceStatus = optString("sourceStatus"),
        evidenceSources = optJSONArray("evidenceSources").toStringList(),
        candidateNodeCount = optInt("candidateNodeCount"),
        confirmedNodeCount = optInt("confirmedNodeCount"),
        timelineItemCount = optInt("timelineItemCount"),
    )
}

private fun JSONArray?.toInteractionTimelineItems(): List<InteractionTimelineItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionTimelineItem>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionTimelineItem(
            itemId = item.optString("itemId"),
            type = item.optString("type"),
            track = item.optString("track"),
            startMs = item.optLong("startMs"),
            endMs = item.optLong("endMs"),
            analyticsKey = item.optString("analyticsKey"),
        )
    }
    return result
}

private fun JSONArray?.toInteractionTimedEvents(): List<InteractionTimedEvent> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionTimedEvent>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionTimedEvent(
            eventId = item.optString("eventId"),
            episodeId = item.optString("episodeId"),
            startMs = item.optLong("startMs"),
            endMs = item.optLong("endMs"),
            componentType = item.optString("componentType"),
            visualStyle = item.optString("visualStyle"),
            placement = item.optString("placement"),
            safeArea = item.optJSONObject("safeArea").toInteractionSafeArea(),
            maxLines = item.optInt("maxLines", 2).coerceAtLeast(1),
            analyticsKey = item.optString("analyticsKey"),
            evidenceRefs = item.optJSONArray("evidenceRefs").toStringList(),
            generationSource = item.optString("generationSource"),
            confidence = item.optDouble("confidence", 0.0),
            reviewStatus = item.optString("reviewStatus"),
            payloadHash = item.optString("payloadHash"),
        )
    }
    return result
}

private fun JSONObject?.toEvidenceGraph(): EvidenceGraph? {
    if (this == null) {
        return null
    }
    return EvidenceGraph(
        episodeId = optString("episodeId"),
        focusTimeMs = optLong("focusTimeMs"),
        sourceStatus = optString("sourceStatus"),
        evidenceSources = optJSONArray("evidenceSources").toStringList(),
        storyFacets = optJSONObject("storyFacets").toEvidenceStoryFacets(),
        explanations = optJSONArray("explanations").toEvidenceGraphExplanations(),
        nodes = optJSONArray("nodes").toEvidenceGraphNodes(),
        evidence = optJSONArray("evidence").toEvidenceGraphItems(),
        relations = optJSONArray("relations").toEvidenceGraphRelations(),
    )
}

private fun JSONObject?.toEvidenceStoryFacets(): EvidenceStoryFacets {
    if (this == null) {
        return EvidenceStoryFacets()
    }
    return EvidenceStoryFacets(
        characters = optJSONArray("characters").toStringList(),
        conflicts = optJSONArray("conflicts").toStringList(),
        reversals = optJSONArray("reversals").toStringList(),
        audienceResonance = optJSONArray("audienceResonance").toStringList(),
    )
}

private fun JSONArray?.toEvidenceGraphExplanations(): List<EvidenceGraphExplanation> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<EvidenceGraphExplanation>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += EvidenceGraphExplanation(
            nodeId = item.optString("nodeId"),
            title = item.optString("title"),
            storyTags = item.optJSONArray("storyTags").toStringList(),
            audienceResonance = item.optString("audienceResonance"),
            evidenceSummary = item.optString("evidenceSummary"),
            explainText = item.optString("explainText"),
            confidence = item.optDouble("confidence", 0.0),
        )
    }
    return result
}

private fun JSONArray?.toEvidenceGraphNodes(): List<EvidenceGraphNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<EvidenceGraphNode>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += EvidenceGraphNode(
            nodeId = item.optString("nodeId"),
            eventId = item.optString("eventId"),
            title = item.optString("title"),
            timeMs = item.optLong("timeMs"),
            endMs = item.optLong("endMs"),
            componentType = item.optString("componentType"),
            generationSource = item.optString("generationSource"),
            reviewStatus = item.optString("reviewStatus"),
            confidence = item.optDouble("confidence", 0.0),
            evidenceRefs = item.optJSONArray("evidenceRefs").toStringList(),
            resolvedEvidenceRefs = item.optJSONArray("resolvedEvidenceRefs").toStringList(),
            whyText = item.optString("whyText"),
        )
    }
    return result
}

private fun JSONArray?.toEvidenceGraphItems(): List<EvidenceGraphItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<EvidenceGraphItem>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += EvidenceGraphItem(
            refId = item.optString("refId"),
            kind = item.optString("kind"),
            sourceLabel = item.optString("sourceLabel"),
            timeMs = item.optLong("timeMs"),
            endMs = item.optLong("endMs"),
            displayText = item.optString("displayText"),
            assetPath = item.optString("assetPath"),
        )
    }
    return result
}

private fun JSONArray?.toEvidenceGraphRelations(): List<EvidenceGraphRelation> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<EvidenceGraphRelation>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += EvidenceGraphRelation(
            fromNodeId = item.optString("fromNodeId"),
            toEvidenceRef = item.optString("toEvidenceRef"),
            relationType = item.optString("relationType"),
            timeDeltaMs = item.optLong("timeDeltaMs"),
        )
    }
    return result
}

private fun JSONArray?.toInteractionCandidateNodes(): List<InteractionCandidateNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionCandidateNode>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionCandidateNode(
            candidateId = item.optString("candidateId"),
            timeMs = item.optLong("timeMs"),
            type = item.optString("type"),
            question = item.optString("question"),
            reason = item.optString("reason"),
            options = item.optJSONArray("options").toStringList(),
            source = item.optString("source"),
            evidenceRefs = item.optJSONArray("evidenceRefs").toStringList(),
            confidence = item.optDouble("confidence", 0.0),
            reviewStatus = item.optString("reviewStatus", "pending"),
            orchestrationAdvice = item.optJSONObject("orchestrationAdvice").toInteractionCandidateOrchestrationAdvice(),
        )
    }
    return result
}

private fun JSONObject?.toInteractionCandidateOrchestrationAdvice(): InteractionCandidateOrchestrationAdvice {
    if (this == null) {
        return InteractionCandidateOrchestrationAdvice()
    }
    return InteractionCandidateOrchestrationAdvice(
        recommendedComponentType = optString("recommendedComponentType"),
        visualStyle = optString("visualStyle"),
        placement = optString("placement"),
        safeArea = optJSONObject("safeArea").toInteractionSafeArea(),
        maxLines = optInt("maxLines", 2),
        analyticsKey = optString("analyticsKey"),
        evidenceSummary = optString("evidenceSummary"),
        publishEligible = optBoolean("publishEligible", false),
    )
}

private fun JSONObject.toInteractionCandidateReviewResult(): InteractionCandidateReviewResult {
    return InteractionCandidateReviewResult(
        candidateId = optString("candidateId"),
        episodeId = optString("episodeId"),
        reviewStatus = optString("reviewStatus"),
        editedQuestion = optString("editedQuestion"),
        editedOptions = optJSONArray("editedOptions").toStringList(),
        reviewNote = optString("reviewNote"),
        reviewedAtMs = optLong("reviewedAtMs"),
    )
}

private fun JSONObject.toDanmakuEmotionReport(): DanmakuEmotionReport {
    return DanmakuEmotionReport(
        episodeId = optString("episodeId"),
        episodeNo = optInt("episodeNo"),
        source = optString("source"),
        summary = optString("summary"),
        items = optJSONArray("items").toDanmakuEmotionPoints(),
    )
}

private fun JSONArray?.toDanmakuEmotionPoints(): List<DanmakuEmotionPoint> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<DanmakuEmotionPoint>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += DanmakuEmotionPoint(
            hotspotId = item.optString("hotspotId"),
            episodeId = item.optString("episodeId"),
            timeMs = item.optLong("timeMs"),
            startMs = item.optLong("startMs"),
            endMs = item.optLong("endMs"),
            keywords = item.optJSONArray("keywords").toStringList(),
            emotion = item.optString("emotion"),
            emotionScore = item.optDouble("emotionScore", 0.0),
            commentIntensity = item.optInt("commentIntensity"),
            likeIntensity = item.optInt("likeIntensity"),
            heatScore = item.optInt("heatScore"),
            suggestedInteraction = item.optString("suggestedInteraction"),
            suggestedComponentType = item.optString("suggestedComponentType"),
            sceneSummary = item.optString("sceneSummary"),
            evidenceRefs = item.optJSONArray("evidenceRefs").toStringList(),
            reviewStatus = item.optString("reviewStatus"),
        )
    }
    return result
}

private fun JSONArray?.toInteractionNodesFromTimeline(): List<InteractionNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionNode>()
    for (index in 0 until length()) {
        val payload = getJSONObject(index).optJSONObject("payload") ?: continue
        result += payload.toInteractionNode()
    }
    return result
}

private fun JSONArray.toInteractionNodes(): List<InteractionNode> {
    val result = mutableListOf<InteractionNode>()
    for (index in 0 until length()) {
        result += getJSONObject(index).toInteractionNode()
    }
    return result
}

private fun JSONObject.toInteractionNode(): InteractionNode {
    val trigger = getJSONObject("trigger")
    val display = optJSONObject("display") ?: JSONObject()
    val aiInsert = optJSONObject("aiInsert") ?: JSONObject()
    val generatedAsset = aiInsert.optJSONObject("generatedAsset") ?: JSONObject()
    val provider = generatedAsset.optJSONObject("provider") ?: JSONObject()
    val generation = optJSONObject("generation") ?: JSONObject()
    return InteractionNode(
        id = getString("id"),
        type = getString("type"),
        title = optString("title"),
        subtitle = optString("subtitle"),
        triggerMs = trigger.optLong("timeMs"),
        displayMode = display.optString("mode", "SOFT"),
        timeoutMs = display.optLong("timeoutMs", 8_000L),
        allowSkip = display.optBoolean("allowSkip", true),
        skipText = display.optString("skipText", "跳过"),
        componentType = display.optString("componentType", optString("componentType", "CHOICE_CARD")),
        analyticsKey = display.optString("analyticsKey", optString("analyticsKey", "interaction_component.${optString("id")}")),
        placement = display.optString("placement", optString("placement", "BOTTOM_CENTER")),
        safeArea = (display.optJSONObject("safeArea") ?: optJSONObject("safeArea")).toInteractionSafeArea(),
        maxLines = display.optInt("maxLines", optInt("maxLines", 2)).coerceAtLeast(1),
        visualStyle = display.optString("visualStyle", display.optString("style", optString("visualStyle", "高光互动"))),
        effectText = display.optString("effectText", "点"),
        badgeText = display.optString("badgeText", "互动"),
        promptText = display.optString("promptText", "选择一个即时反应"),
        aiInsertTitle = aiInsert.optString("title"),
        aiInsertDescription = aiInsert.optString("description"),
        aiInsertMediaUrl = generatedAsset.optString("mediaUrl"),
        aiInsertMediaType = generatedAsset.optString("mediaType"),
        aiInsertHighEnergyLine = generatedAsset.optString("highEnergyLine"),
        aiInsertProviderName = provider.optString("name"),
        options = optJSONArray("options").toInteractionOptions(),
        evidenceRefs = generation.optJSONArray("evidenceRefs").toStringList(),
        generationSource = generation.optString("generationSource", "manual"),
        confidence = generation.optDouble("confidence", 0.0),
        reviewStatus = generation.optString("reviewStatus"),
    )
}

private fun JSONObject?.toInteractionSafeArea(): InteractionSafeArea {
    if (this == null) {
        return InteractionSafeArea()
    }
    return InteractionSafeArea(
        topDp = optInt("topDp", 24),
        bottomDp = optInt("bottomDp", 24),
        startDp = optInt("startDp", 16),
        endDp = optInt("endDp", 16),
        avoidRightRail = optBoolean("avoidRightRail", optBoolean("avoidRightActions", false)),
        avoidDanmaku = optBoolean("avoidDanmaku", optBoolean("avoidDanmakuLayer", false)),
        avoidProgressBar = optBoolean("avoidProgressBar", optBoolean("avoidBottomControls", false)),
    )
}

private fun JSONArray?.toInteractionOptions(): List<InteractionOption> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionOption>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionOption(
            id = item.getString("id"),
            text = item.optString("text"),
            branch = item.optJSONObject("branch").toInteractionBranch(),
        )
    }
    return result
}

private fun JSONObject?.toInteractionBranch(): InteractionBranch? {
    if (this == null) {
        return null
    }
    val returnObject = optJSONObject("return") ?: return null
    return InteractionBranch(
        segmentId = optString("segmentId"),
        startMs = optLong("startMs"),
        endMs = optLong("endMs"),
        returnSeekMs = returnObject.optLong("seekTimeMs"),
        mediaUrl = optString("mediaUrl"),
        mediaType = optString("mediaType"),
        playbackMode = optString("playbackMode", "REPLACE_MAIN"),
    )
}

private fun JSONObject.toInteractionSubmitResult(): InteractionSubmitResult {
    val feedback = optJSONObject("feedback") ?: JSONObject()
    val reward = optJSONObject("reward") ?: JSONObject()
    val nextAction = optJSONObject("nextAction") ?: JSONObject()
    val growthValue = reward.optInt("growthValue", 0)
    val points = reward.optInt("points", 0)
    return InteractionSubmitResult(
        recordId = optString("recordId"),
        feedbackText = feedback.optString("text", "互动已提交"),
        rewardText = "成长值 +$growthValue，积分 +$points",
        nextActionType = nextAction.optString("type", "CONTINUE"),
        aggregate = optJSONObject("aggregate").toIntMap(),
    )
}

private fun JSONObject.toInteractionInsights(): InteractionInsights {
    return InteractionInsights(
        episodeId = optString("episodeId"),
        durationMs = optLong("durationMs"),
        totalInteractions = optInt("totalInteractions"),
        nodeCount = optInt("nodeCount"),
        peakNodeId = optString("peakNodeId"),
        peakNodeTitle = optString("peakNodeTitle"),
        crowdSummary = optString("crowdSummary"),
        nodes = optJSONArray("nodes").toInteractionHeatNodes(),
    )
}

private fun JSONArray?.toInteractionHeatNodes(): List<InteractionHeatNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionHeatNode>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionHeatNode(
            nodeId = item.optString("nodeId"),
            title = item.optString("title"),
            style = item.optString("style"),
            effectText = item.optString("effectText"),
            badgeText = item.optString("badgeText"),
            triggerMs = item.optLong("triggerMs"),
            heatScore = item.optInt("heatScore"),
            totalCount = item.optInt("totalCount"),
            liveCount = item.optInt("liveCount"),
            options = item.optJSONArray("options").toInteractionOptionStats(),
        )
    }
    return result
}

private fun JSONArray?.toInteractionOptionStats(): List<InteractionOptionStat> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<InteractionOptionStat>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionOptionStat(
            optionId = item.optString("optionId"),
            optionText = item.optString("optionText"),
            count = item.optInt("count"),
            liveCount = item.optInt("liveCount"),
            percent = item.optInt("percent"),
        )
    }
    return result
}

private fun JSONObject.toTelemetryDispatchResult(): TelemetryDispatchResult {
    return TelemetryDispatchResult(
        acceptedIds = optJSONArray("accepted_ids").toStringList(),
        retryableIds = optJSONArray("retryable_ids").toStringList(),
    )
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<String>()
    for (index in 0 until length()) {
        result += optString(index)
    }
    return result
}

private fun JSONArray.toWatchHistoryItems(baseUrl: String): List<WatchHistoryItem> {
    val result = mutableListOf<WatchHistoryItem>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += WatchHistoryItem(
            dramaId = item.optString("drama_id"),
            dramaTitle = item.optString("drama_title"),
            episodeId = item.optString("episode_id"),
            episodeTitle = item.optString("episode_title"),
            playUrl = item.optString("play_url", "$baseUrl/media/episodes/${item.optString("episode_id")}"),
            lastProgressMs = item.optLong("last_progress_ms"),
            durationMs = item.optLong("duration_ms"),
            isCompleted = item.optBoolean("is_completed"),
            updatedAtMs = item.optLong("updated_at_ms"),
        )
    }
    return result
}

private fun JSONObject?.toIntMap(): Map<String, Int> {
    if (this == null) {
        return emptyMap()
    }
    val result = linkedMapOf<String, Int>()
    val iterator = keys()
    while (iterator.hasNext()) {
        val key = iterator.next()
        result[key] = optInt(key)
    }
    return result
}

private fun JSONArray.toEpisodeCards(baseUrl: String): List<EpisodeCard> {
    val result = mutableListOf<EpisodeCard>()
    for (index in 0 until length()) {
        result += getJSONObject(index).toEpisodeCard(baseUrl)
    }
    return result
}

private fun JSONObject.toEpisodeCard(baseUrl: String): EpisodeCard {
    return EpisodeCard(
        episodeId = getString("episode_id"),
        episodeNo = optInt("episode_no", 1),
        title = optString("title", "第${optInt("episode_no", 1)}集"),
        durationMs = optLong("duration_ms"),
        summary = optString("summary"),
        playUrl = optString("play_url", "$baseUrl/media/episodes/${getString("episode_id")}"),
    )
}

private fun JSONObject.toStorySummaryCacheStatus(): StorySummaryCacheStatus {
    return StorySummaryCacheStatus(
        dramaId = optString("drama_id"),
        promptVersion = optString("prompt_version"),
        source = optString("source"),
        status = optString("status"),
        generatedAtMs = optLong("generated_at_ms", optLong("generated_at")),
        modelName = optString("model_name"),
        latencyMs = optLong("latency_ms"),
        degradeReason = optString("degrade_reason"),
        dramaDescription = optString("drama_description"),
        episodes = optJSONArray("episodes").toStorySummaryEpisodes(),
        latestAttempt = optJSONObject("latest_attempt").toStorySummaryCacheAttempt(),
    )
}

private fun JSONArray?.toShareableMoments(): List<ShareableMoment> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<ShareableMoment>()
    for (index in 0 until length()) {
        result += getJSONObject(index).toShareableMoment()
    }
    return result
}

private fun JSONObject.toShareableMoment(): ShareableMoment {
    return ShareableMoment(
        momentId = optString("momentId"),
        dramaId = optString("dramaId"),
        episodeId = optString("episodeId"),
        episodeNo = optInt("episodeNo"),
        episodeTitle = optString("episodeTitle"),
        startMs = optLong("startMs"),
        endMs = optLong("endMs"),
        title = optString("title"),
        hookText = optString("hookText"),
        sourceNodeId = optString("sourceNodeId"),
        source = optString("source"),
        selectionStrategy = optString("selectionStrategy"),
        heatScore = optInt("heatScore"),
        playUrl = optString("playUrl"),
        savedAtMs = optLong("savedAtMs"),
    )
}

private fun JSONObject.toDemoRoutePlan(): DemoRoutePlan {
    return DemoRoutePlan(
        routeId = optString("routeId"),
        dramaId = optString("dramaId"),
        title = optString("title"),
        source = optString("source"),
        entry = (optJSONObject("entry") ?: JSONObject()).toDemoRouteEntry(),
        steps = optJSONArray("steps").toDemoRouteSteps(),
        checks = (optJSONObject("checks") ?: JSONObject()).toDemoRouteChecks(),
    )
}

private fun JSONObject.toDemoRouteEntry(): DemoRouteEntry {
    return DemoRouteEntry(
        episodeId = optString("episodeId"),
        startMs = optLong("startMs", 0L),
        momentId = optString("momentId"),
        title = optString("title"),
    )
}

private fun JSONArray?.toDemoRouteSteps(): List<DemoRouteStep> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<DemoRouteStep>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += DemoRouteStep(
            stepId = item.optString("stepId"),
            order = item.optInt("order", index + 1),
            title = item.optString("title"),
            description = item.optString("description"),
            actionType = item.optString("actionType"),
            api = item.optString("api"),
            status = item.optString("status"),
            episodeId = item.optString("episodeId"),
            startMs = item.optLong("startMs", 0L),
            evidenceCount = item.optInt("evidenceCount", 0),
        )
    }
    return result
}

private fun JSONObject.toDemoRouteChecks(): DemoRouteChecks {
    return DemoRouteChecks(
        usesFakeData = optBoolean("usesFakeData", false),
        restartSafe = optBoolean("restartSafe", false),
        homeFallbackAvailable = optBoolean("homeFallbackAvailable", false),
        sqliteBacked = optBoolean("sqliteBacked", false),
        evidenceGraphAvailable = optBoolean("evidenceGraphAvailable", false),
    )
}

private fun JSONObject.toDefenseDemoModeStatus(): DefenseDemoModeStatus {
    return DefenseDemoModeStatus(
        enabled = optBoolean("enabled", false),
        routeId = optString("routeId"),
        dramaId = optString("dramaId"),
        title = optString("title"),
        description = optString("description"),
        fixedStrategy = optString("fixedStrategy", "heat_score_desc_v1"),
        contentSource = optString("contentSource"),
        entry = (optJSONObject("entry") ?: JSONObject()).toDemoRouteEntry(),
        quickSteps = optJSONArray("quickSteps").toDefenseDemoQuickSteps(),
        fallbacks = (optJSONObject("fallbacks") ?: JSONObject()).toDefenseDemoFallbacks(),
    )
}

private fun JSONArray?.toDefenseDemoQuickSteps(): List<DefenseDemoQuickStep> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<DefenseDemoQuickStep>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += DefenseDemoQuickStep(
            stepId = item.optString("stepId"),
            title = item.optString("title"),
            actionType = item.optString("actionType"),
            status = item.optString("status"),
            api = item.optString("api"),
        )
    }
    return result
}

private fun JSONObject.toDefenseDemoFallbacks(): DefenseDemoFallbacks {
    return DefenseDemoFallbacks(
        homeFallbackAvailable = optBoolean("homeFallbackAvailable", false),
        sqliteBacked = optBoolean("sqliteBacked", false),
        evidenceGraphAvailable = optBoolean("evidenceGraphAvailable", false),
        lastSuccessArtifactAvailable = optBoolean("lastSuccessArtifactAvailable", false),
    )
}

private fun ShareableMoment.toJsonObject(): JSONObject {
    return JSONObject()
        .put("momentId", momentId)
        .put("dramaId", dramaId)
        .put("episodeId", episodeId)
        .put("episodeNo", episodeNo)
        .put("episodeTitle", episodeTitle)
        .put("startMs", startMs)
        .put("endMs", endMs)
        .put("title", title)
        .put("hookText", hookText)
        .put("sourceNodeId", sourceNodeId)
        .put("source", source)
        .put("selectionStrategy", selectionStrategy)
        .put("heatScore", heatScore)
        .put("playUrl", playUrl)
}

private fun JSONObject?.toStorySummaryCacheAttempt(): StorySummaryCacheAttempt {
    if (this == null) {
        return StorySummaryCacheAttempt(
            source = "",
            status = "missing",
            generatedAtMs = 0L,
            modelName = "",
            latencyMs = 0L,
            degradeReason = "",
        )
    }
    return StorySummaryCacheAttempt(
        source = optString("source"),
        status = optString("status"),
        generatedAtMs = optLong("generated_at_ms", optLong("generated_at")),
        modelName = optString("model_name"),
        latencyMs = optLong("latency_ms"),
        degradeReason = optString("degrade_reason"),
    )
}

private fun JSONArray?.toStorySummaryEpisodes(): List<StorySummaryEpisode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<StorySummaryEpisode>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += StorySummaryEpisode(
            episodeId = item.optString("episode_id"),
            episodeNo = item.optInt("episode_no"),
            summary = item.optString("summary"),
        )
    }
    return result
}

private fun JSONArray?.toDramaCharacters(): List<DramaCharacter> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<DramaCharacter>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += DramaCharacter(
            characterId = item.optString("character_id"),
            name = item.optString("name"),
            avatarUrl = item.optString("avatar_url"),
        )
    }
    return result
}

private fun JSONObject.optStringArray(key: String): List<String> {
    val items = optJSONArray(key) ?: return emptyList()
    val result = mutableListOf<String>()
    for (index in 0 until items.length()) {
        result += items.optString(index)
    }
    return result
}

private fun JSONObject.toAiContentRecapResult(): AiContentRecapResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiContentRecapResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        summary = result.optString("summary"),
        highlights = result.optJSONArray("highlights").toStringList(),
        characterFocus = result.optJSONArray("character_focus").toStringList(),
        discussionSeeds = result.optJSONArray("discussion_seeds").toStringList(),
        continueReason = result.optString("continue_reason"),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiInteractionFeedbackResult(): AiInteractionFeedbackResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiInteractionFeedbackResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        feedbackText = result.optString("feedback_text"),
        selectionExplanation = result.optString("selection_explanation"),
        followupQuestion = result.optString("followup_question"),
        derivedTags = result.optJSONArray("derived_tags").toAiTagItems(),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiTagExtractResult(): AiTagExtractResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiTagExtractResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        contentTags = result.optJSONArray("content_tags").toAiTagItems(),
        interactionTags = result.optJSONArray("interaction_tags").toAiTagItems(),
        userProfileTagUpdates = result.optJSONArray("user_profile_tag_updates").toAiProfileTagUpdates(),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiModerationResult(): AiModerationResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiModerationResult(
        status = optString("status", "ok"),
        decision = result.optString("decision"),
        riskFlags = result.optJSONArray("risk_flags").toStringList(),
        matchedKeywords = result.optJSONArray("matched_keywords").toStringList(),
        reviewText = result.optString("review_text"),
        blockReason = optString("block_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiDiscussionSeedResult(): AiDiscussionSeedResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiDiscussionSeedResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        discussionQuestions = result.optJSONArray("discussion_questions").toStringList(),
        characterPerspectives = result.optJSONArray("character_perspectives").toAiCharacterPerspectives(),
        nextEpisodePredictions = result.optJSONArray("next_episode_predictions").toStringList(),
        alternateChoiceTopics = result.optJSONArray("alternate_choice_topics").toStringList(),
        shareText = result.optString("share_text"),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiStoryContinuationResult(): AiStoryContinuationResult {
    val result = optJSONObject("result") ?: JSONObject()
    val asset = result.optJSONObject("generated_asset") ?: JSONObject()
    val provider = asset.optJSONObject("provider") ?: JSONObject()
    val playback = asset.optJSONObject("playback") ?: JSONObject()
    val remoteAttempt = asset.optJSONObject("remoteAttempt") ?: JSONObject()
    val mediaAsset = asset.optJSONObject("assetCache").toGeneratedMediaAsset()
    return AiStoryContinuationResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        episodeId = result.optString("episode_id"),
        title = result.optString("continuation_title"),
        summary = result.optString("continuation_summary"),
        sceneDirection = result.optString("scene_direction"),
        dialogueLines = result.optJSONArray("dialogue_lines").toStringList(),
        viewerHook = result.optString("viewer_hook"),
        mediaUrl = asset.optString("mediaUrl"),
        mediaType = asset.optString("mediaType"),
        mediaAsset = mediaAsset,
        providerName = provider.optString("name"),
        providerMode = provider.optString("mode"),
        remoteAttemptStatus = remoteAttempt.optString("status"),
        remoteAttemptReason = remoteAttempt.optString("degradeReason"),
        referenceStatus = remoteAttempt.optString("referenceStatus"),
        playbackMode = playback.optString("mode", "POST_EPISODE_CONTINUATION"),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAgnesStatusResult(): AgnesStatusResult {
    return AgnesStatusResult(
        configured = optBoolean("configured", false),
        source = optString("source"),
        baseUrl = optString("baseUrl"),
        imageModel = optString("imageModel"),
        videoModel = optString("videoModel"),
    )
}

private fun JSONObject.toAiCheckinCardResult(): AiCheckinCardResult {
    val result = optJSONObject("result") ?: JSONObject()
    val mediaAsset = result.optJSONObject("assetCache").toGeneratedMediaAsset()
    return AiCheckinCardResult(
        status = optString("status", "degraded"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        title = result.optString("title"),
        prompt = result.optString("prompt"),
        imageUrl = result.optString("imageUrl"),
        remoteImageUrl = result.optString("remoteImageUrl"),
        mediaAsset = mediaAsset,
        provider = result.optString("provider"),
        style = result.optString("style"),
        styleLabel = result.optString("styleLabel"),
        episodeId = result.optString("episodeId"),
        momentId = result.optString("momentId"),
        cardStatus = result.optString("status"),
        cardLatencyMs = result.optLong("latencyMs", 0L),
        cardDegradeReason = result.optString("degradeReason"),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toGenerationTaskResult(): GenerationTaskResult {
    val result = optJSONObject("result") ?: JSONObject()
    val lastSuccess = optJSONObject("lastSuccess") ?: JSONObject()
    val mediaAsset = result.optJSONObject("assetCache").toGeneratedMediaAsset()
    return GenerationTaskResult(
        taskId = optString("taskId"),
        taskType = optString("taskType"),
        dramaId = optString("dramaId"),
        episodeId = optString("episodeId"),
        status = optString("status"),
        provider = optString("provider"),
        modelName = optString("modelName"),
        mediaUrl = optString("mediaUrl"),
        mediaType = optString("mediaType"),
        mediaAsset = mediaAsset,
        latencyMs = optLong("latencyMs", 0L),
        degradeReason = optString("degradeReason"),
        resultTitle = result.optString("title"),
        providerMode = result.optString("providerMode"),
        createdAtMs = optLong("createdAtMs", 0L),
        updatedAtMs = optLong("updatedAtMs", 0L),
        lastSuccess = GenerationTaskLastSuccess(
            taskId = lastSuccess.optString("taskId"),
            mediaUrl = lastSuccess.optString("mediaUrl"),
            mediaType = lastSuccess.optString("mediaType"),
            provider = lastSuccess.optString("provider"),
            mediaAsset = lastSuccess.optJSONObject("assetCache").toGeneratedMediaAsset(),
            updatedAtMs = lastSuccess.optLong("updatedAtMs", 0L),
        ),
    )
}

private fun JSONObject?.toGeneratedMediaAsset(): GeneratedMediaAsset {
    if (this == null) {
        return GeneratedMediaAsset()
    }
    return GeneratedMediaAsset(
        assetId = optString("assetId"),
        remoteUrl = optString("remoteUrl"),
        localUrl = optString("localUrl"),
        mediaUrl = optString("mediaUrl"),
        contentType = optString("contentType", optString("mediaType")),
        cacheStatus = optString("cacheStatus"),
        byteSize = optLong("byteSize", 0L),
        degradeReason = optString("degradeReason"),
    )
}

private fun JSONObject.toGeneratedAssetManagementResult(): GeneratedAssetManagementResult {
    return GeneratedAssetManagementResult(
        dramaId = optString("dramaId"),
        summary = (optJSONObject("summary") ?: JSONObject()).toGeneratedAssetManagementSummary(),
        recentSuccesses = optJSONArray("recentSuccesses").toGeneratedAssetManagementItems(),
        failedAttempts = optJSONArray("failedAttempts").toGeneratedAssetManagementItems(),
    )
}

private fun JSONObject.toGeneratedAssetManagementSummary(): GeneratedAssetManagementSummary {
    return GeneratedAssetManagementSummary(
        successCount = optInt("successCount", 0),
        failedCount = optInt("failedCount", 0),
        cachedByteSize = optLong("cachedByteSize", 0L),
        source = optString("source"),
    )
}

private fun JSONArray?.toGeneratedAssetManagementItems(): List<GeneratedAssetManagementItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<GeneratedAssetManagementItem>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += GeneratedAssetManagementItem(
            taskId = item.optString("taskId"),
            taskType = item.optString("taskType"),
            dramaId = item.optString("dramaId"),
            episodeId = item.optString("episodeId"),
            status = item.optString("status"),
            provider = item.optString("provider"),
            modelName = item.optString("modelName"),
            mediaUrl = item.optString("mediaUrl"),
            mediaType = item.optString("mediaType"),
            latencyMs = item.optLong("latencyMs", 0L),
            degradeReason = item.optString("degradeReason"),
            title = item.optString("title"),
            updatedAtMs = item.optLong("updatedAtMs", 0L),
            mediaAsset = item.optJSONObject("assetCache").toGeneratedMediaAsset(),
        )
    }
    return result
}

private fun JSONObject.toGeneratedAssetCleanupResult(): GeneratedAssetCleanupResult {
    return GeneratedAssetCleanupResult(
        dramaId = optString("dramaId"),
        deletedCount = optInt("deletedCount", 0),
        statuses = optJSONArray("statuses").toStringList(),
    )
}

private fun JSONObject.toAiHistoryRecapResult(): AiHistoryRecapResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiHistoryRecapResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        items = result.optJSONArray("items").toAiHistoryRecapItems(),
        summary = result.optString("summary"),
        nextEpisodeId = result.optString("next_episode_id"),
        continueReason = result.optString("continue_reason"),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiHomeRecommendResult(): AiHomeRecommendResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiHomeRecommendResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        items = result.optJSONArray("items").toAiHomeRecommendItems(),
        strategy = result.optString("strategy"),
        personalizationSignals = result.optJSONArray("personalization_signals").toStringList(),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toOperationsDashboardResult(): OperationsDashboardResult {
    return OperationsDashboardResult(
        storage = optJSONObject("storage").toOperationsDashboardStorage(),
        dramaId = optString("dramaId"),
        episodeId = optString("episodeId"),
        generatedAtMs = optLong("generatedAtMs"),
        overview = optJSONObject("overview").toOperationsDashboardOverview(),
        trend = optJSONArray("trend").toOperationsDashboardTrendPoints(),
        trendSummary = optJSONObject("trendSummary").toOperationsDashboardTrendSummary(),
        hotNodes = optJSONArray("hotNodes").toOperationsDashboardHotNodes(),
        ai = optJSONObject("ai").toOperationsDashboardAiSummary(),
        highlightStrategies = optJSONArray("highlightStrategies").toOperationsDashboardHighlightStrategies(),
        agnesGeneration = optJSONObject("agnesGeneration").toOperationsDashboardAgnesGeneration(),
        profile = optJSONObject("profile").toOperationsDashboardProfileSummary(),
    )
}

private fun JSONObject?.toOperationsDashboardStorage(): OperationsDashboardStorage {
    if (this == null) {
        return OperationsDashboardStorage(engine = "", persistent = false)
    }
    return OperationsDashboardStorage(
        engine = optString("engine"),
        persistent = optBoolean("persistent"),
    )
}

private fun JSONObject?.toOperationsDashboardOverview(): OperationsDashboardOverview {
    if (this == null) {
        return OperationsDashboardOverview(
            interactionCtr = 0.0,
            interactionImpressions = 0,
            interactionSubmits = 0,
            interactionCount = 0,
            insertPlaybackCompletionRate = 0.0,
            insertPlaybackStarts = 0,
            insertPlaybackCompleted = 0,
            aiSuccessRate = 0.0,
            aiDegradedRate = 0.0,
            aiP95LatencyMs = 0L,
            watchEpisodeCount = 0,
            watchCompletedCount = 0,
            videoStartAttempts = 0,
            firstFrameRendered = 0,
            startupSuccessRate = 0.0,
            startupFailureRate = 0.0,
            exitBeforeStartCount = 0,
            rebufferCount = 0,
            rebufferTotalMs = 0L,
            startupP50Ms = 0L,
            startupP95Ms = 0L,
            rebufferP95Ms = 0L,
            savedMomentCount = 0,
            eventCount = 0,
        )
    }
    return OperationsDashboardOverview(
        interactionCtr = optDouble("interactionCtr"),
        interactionImpressions = optInt("interactionImpressions"),
        interactionSubmits = optInt("interactionSubmits"),
        interactionCount = optInt("interactionCount"),
        insertPlaybackCompletionRate = optDouble("insertPlaybackCompletionRate"),
        insertPlaybackStarts = optInt("insertPlaybackStarts"),
        insertPlaybackCompleted = optInt("insertPlaybackCompleted"),
        aiSuccessRate = optDouble("aiSuccessRate"),
        aiDegradedRate = optDouble("aiDegradedRate"),
        aiP95LatencyMs = optLong("aiP95LatencyMs"),
        watchEpisodeCount = optInt("watchEpisodeCount"),
        watchCompletedCount = optInt("watchCompletedCount"),
        videoStartAttempts = optInt("videoStartAttempts"),
        firstFrameRendered = optInt("firstFrameRendered"),
        startupSuccessRate = optDouble("startupSuccessRate"),
        startupFailureRate = optDouble("startupFailureRate"),
        exitBeforeStartCount = optInt("exitBeforeStartCount"),
        rebufferCount = optInt("rebufferCount"),
        rebufferTotalMs = optLong("rebufferTotalMs"),
        startupP50Ms = optLong("startupP50Ms"),
        startupP95Ms = optLong("startupP95Ms"),
        rebufferP95Ms = optLong("rebufferP95Ms"),
        savedMomentCount = optInt("savedMomentCount"),
        eventCount = optInt("eventCount"),
    )
}

private fun JSONArray?.toOperationsDashboardTrendPoints(): List<OperationsDashboardTrendPoint> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardTrendPoint>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardTrendPoint(
            day = item.optString("day"),
            label = item.optString("label"),
            interactionImpressions = item.optInt("interactionImpressions"),
            interactionSubmits = item.optInt("interactionSubmits"),
            interactionCtr = item.optDouble("interactionCtr"),
            watchEpisodeCount = item.optInt("watchEpisodeCount"),
            watchCompletedCount = item.optInt("watchCompletedCount"),
            watchCompletionRate = item.optDouble("watchCompletionRate"),
            insertPlaybackStarts = item.optInt("insertPlaybackStarts"),
            insertPlaybackCompleted = item.optInt("insertPlaybackCompleted"),
            insertPlaybackCompletionRate = item.optDouble("insertPlaybackCompletionRate"),
            videoStartAttempts = item.optInt("videoStartAttempts"),
            firstFrameRendered = item.optInt("firstFrameRendered"),
            startupSuccessRate = item.optDouble("startupSuccessRate"),
            startupFailureRate = item.optDouble("startupFailureRate"),
            exitBeforeStartCount = item.optInt("exitBeforeStartCount"),
            rebufferCount = item.optInt("rebufferCount"),
            rebufferTotalMs = item.optLong("rebufferTotalMs"),
            startupP95Ms = item.optLong("startupP95Ms"),
            rebufferP95Ms = item.optLong("rebufferP95Ms"),
            playbackErrorCount = item.optInt("playbackErrorCount"),
            fullscreenExitCount = item.optInt("fullscreenExitCount"),
            continueWatchCount = item.optInt("continueWatchCount"),
            aiAttemptCount = item.optInt("aiAttemptCount"),
            aiSuccessCount = item.optInt("aiSuccessCount"),
            aiDegradedCount = item.optInt("aiDegradedCount"),
            aiBlockedCount = item.optInt("aiBlockedCount"),
            aiSuccessRate = item.optDouble("aiSuccessRate"),
            aiDegradedRate = item.optDouble("aiDegradedRate"),
            aiP95LatencyMs = item.optLong("aiP95LatencyMs"),
        )
    }
    return result
}

private fun JSONObject?.toOperationsDashboardTrendSummary(): OperationsDashboardTrendSummary {
    if (this == null) {
        return OperationsDashboardTrendSummary(
            activeDayCount = 0,
            bestCtrDay = "",
            bestCtr = 0.0,
            bestStrategy = "",
            bestStrategyLabel = "",
            bestStrategyCtr = 0.0,
            qualityStatus = "",
            riskNotes = emptyList(),
        )
    }
    return OperationsDashboardTrendSummary(
        activeDayCount = optInt("activeDayCount"),
        bestCtrDay = optString("bestCtrDay"),
        bestCtr = optDouble("bestCtr"),
        bestStrategy = optString("bestStrategy"),
        bestStrategyLabel = optString("bestStrategyLabel"),
        bestStrategyCtr = optDouble("bestStrategyCtr"),
        qualityStatus = optString("qualityStatus"),
        riskNotes = optJSONArray("riskNotes").toStringList(),
    )
}

private fun JSONArray?.toOperationsDashboardHotNodes(): List<OperationsDashboardHotNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardHotNode>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardHotNode(
            nodeId = item.optString("nodeId"),
            nodeTitle = item.optString("nodeTitle"),
            impressions = item.optInt("impressions"),
            submits = item.optInt("submits"),
            ctr = item.optDouble("ctr"),
            choices = item.optJSONArray("choices").toOperationsDashboardChoices(),
        )
    }
    return result
}

private fun JSONArray?.toOperationsDashboardChoices(): List<OperationsDashboardChoice> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardChoice>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardChoice(
            optionId = item.optString("optionId"),
            optionText = item.optString("optionText"),
            selects = item.optInt("selects"),
        )
    }
    return result
}

private fun JSONObject?.toOperationsDashboardAiSummary(): OperationsDashboardAiSummary {
    if (this == null) {
        return OperationsDashboardAiSummary(
            total = 0,
            successCount = 0,
            degradedCount = 0,
            blockedCount = 0,
            successRate = 0.0,
            degradedRate = 0.0,
            p95LatencyMs = 0L,
            capabilities = emptyList(),
        )
    }
    return OperationsDashboardAiSummary(
        total = optInt("total"),
        successCount = optInt("successCount"),
        degradedCount = optInt("degradedCount"),
        blockedCount = optInt("blockedCount"),
        successRate = optDouble("successRate"),
        degradedRate = optDouble("degradedRate"),
        p95LatencyMs = optLong("p95LatencyMs"),
        capabilities = optJSONArray("capabilities").toOperationsDashboardAiCapabilities(),
    )
}

private fun JSONArray?.toOperationsDashboardAiCapabilities(): List<OperationsDashboardAiCapability> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardAiCapability>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardAiCapability(
            capability = item.optString("capability"),
            total = item.optInt("total"),
            successCount = item.optInt("successCount"),
            degradedCount = item.optInt("degradedCount"),
            blockedCount = item.optInt("blockedCount"),
            successRate = item.optDouble("successRate"),
            degradedRate = item.optDouble("degradedRate"),
            p95LatencyMs = item.optLong("p95LatencyMs"),
            latestAtMs = item.optLong("latestAtMs"),
        )
    }
    return result
}

private fun JSONObject?.toOperationsDashboardAgnesGeneration(): OperationsDashboardAgnesGeneration {
    if (this == null) {
        return OperationsDashboardAgnesGeneration(
            totalStarts = 0,
            totalSuccess = 0,
            totalDegraded = 0,
            successRate = 0.0,
            degradedRate = 0.0,
            p95LatencyMs = 0L,
            localTemplateFallbackCount = 0,
            latestAtMs = 0L,
            image = (null as JSONObject?).toOperationsDashboardAgnesBucket(),
            video = (null as JSONObject?).toOperationsDashboardAgnesBucket(),
        )
    }
    return OperationsDashboardAgnesGeneration(
        totalStarts = optInt("totalStarts"),
        totalSuccess = optInt("totalSuccess"),
        totalDegraded = optInt("totalDegraded"),
        successRate = optDouble("successRate"),
        degradedRate = optDouble("degradedRate"),
        p95LatencyMs = optLong("p95LatencyMs"),
        localTemplateFallbackCount = optInt("localTemplateFallbackCount"),
        latestAtMs = optLong("latestAtMs"),
        image = optJSONObject("image").toOperationsDashboardAgnesBucket(),
        video = optJSONObject("video").toOperationsDashboardAgnesBucket(),
    )
}

private fun JSONObject?.toOperationsDashboardAgnesBucket(): OperationsDashboardAgnesBucket {
    if (this == null) {
        return OperationsDashboardAgnesBucket(
            starts = 0,
            success = 0,
            degraded = 0,
            successRate = 0.0,
            degradedRate = 0.0,
            p95LatencyMs = 0L,
        )
    }
    return OperationsDashboardAgnesBucket(
        starts = optInt("starts"),
        success = optInt("success"),
        degraded = optInt("degraded"),
        successRate = optDouble("successRate"),
        degradedRate = optDouble("degradedRate"),
        p95LatencyMs = optLong("p95LatencyMs"),
    )
}

private fun JSONArray?.toOperationsDashboardHighlightStrategies(): List<OperationsDashboardHighlightStrategy> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardHighlightStrategy>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardHighlightStrategy(
            selectionStrategy = item.optString("selectionStrategy"),
            label = item.optString("label"),
            impressions = item.optInt("impressions"),
            clicks = item.optInt("clicks"),
            ctr = item.optDouble("ctr"),
            jumps = item.optInt("jumps"),
            jumpRate = item.optDouble("jumpRate"),
            playCompleted = item.optInt("playCompleted"),
            completionRate = item.optDouble("completionRate"),
            saved = item.optInt("saved"),
            saveRate = item.optDouble("saveRate"),
            averageRank = item.optDouble("averageRank"),
            averageHeatScore = item.optDouble("averageHeatScore"),
            uniqueMomentCount = item.optInt("uniqueMomentCount"),
            latestAtMs = item.optLong("latestAtMs"),
        )
    }
    return result
}

private fun JSONObject?.toOperationsDashboardProfileSummary(): OperationsDashboardProfileSummary {
    if (this == null) {
        return OperationsDashboardProfileSummary(
            interestTags = emptyList(),
            interestTagDistribution = emptyList(),
            recommendReason = "",
            topNodes = emptyList(),
        )
    }
    return OperationsDashboardProfileSummary(
        interestTags = optJSONArray("interestTags").toStringList(),
        interestTagDistribution = optJSONArray("interestTagDistribution").toOperationsDashboardTagDistribution(),
        recommendReason = optString("recommendReason"),
        topNodes = optJSONArray("topNodes").toOperationsDashboardTopNodes(),
    )
}

private fun JSONArray?.toOperationsDashboardTagDistribution(): List<OperationsDashboardTagDistribution> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardTagDistribution>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardTagDistribution(
            tag = item.optString("tag"),
            count = item.optInt("count"),
        )
    }
    return result
}

private fun JSONArray?.toOperationsDashboardTopNodes(): List<OperationsDashboardTopNode> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<OperationsDashboardTopNode>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += OperationsDashboardTopNode(
            nodeId = item.optString("nodeId"),
            nodeTitle = item.optString("nodeTitle"),
            submits = item.optInt("submits"),
        )
    }
    return result
}

private fun JSONObject.toAiVideoUnderstandingResult(): AiVideoUnderstandingResult {
    val result = optJSONObject("result") ?: JSONObject()
    return AiVideoUnderstandingResult(
        status = optString("status", "ok"),
        cached = optBoolean("cached", false),
        latencyMs = optLong("latency_ms", 0L),
        modelName = optJSONObject("model")?.optString("model_name", "") ?: "",
        episodeId = result.optString("episode_id"),
        summary = result.optString("summary"),
        segments = result.optJSONArray("segments").toAiVideoSegments(),
        characters = result.optJSONArray("characters").toAiVideoCharacters(),
        interactionCandidates = result.optJSONArray("interaction_candidates").toAiVideoInteractionCandidates(),
        evidence = result.optJSONArray("evidence").toStringList(),
        productionNotes = result.optJSONArray("production_notes").toStringList(),
        screenTextCues = result.optJSONArray("screen_text_cues").toAiVideoScreenTextCues(),
        audioText = result.optJSONObject("audio_text").toAiVideoAudioText(),
        frameSampling = result.optJSONObject("frame_sampling").toAiVideoFrameSampling(),
        artifact = toAiArtifactMeta(),
        degradeReason = optString("degrade_reason").takeIf { it.isNotBlank() },
    )
}

private fun JSONObject.toAiArtifactMeta(): AiArtifactMeta {
    val artifact = optJSONObject("artifact") ?: JSONObject()
    return AiArtifactMeta(
        source = artifact.optString("source"),
        version = artifact.optInt("version"),
        restoredFromLastSuccess = artifact.optBoolean("restored_from_last_success", false),
        lastSuccessVersion = artifact.optInt("last_success_version"),
        lastSuccessSource = artifact.optString("last_success_source"),
        lastSuccessAtMs = artifact.optLong("last_success_at_ms"),
    )
}

private fun JSONObject?.toAiVideoFrameSampling(): AiVideoFrameSampling {
    if (this == null) {
        return AiVideoFrameSampling(strategy = "", selectedFrames = emptyList())
    }
    val selectedFrames = mutableListOf<AiVideoFrameSample>()
    val rawFrames = optJSONArray("selected_frames")
    if (rawFrames != null) {
        for (index in 0 until rawFrames.length()) {
            val item = rawFrames.optJSONObject(index) ?: continue
            selectedFrames += AiVideoFrameSample(
                timeMs = item.optLong("time_ms"),
                source = item.optString("source"),
                reason = item.optString("reason"),
                score = item.optDouble("score", 0.0),
            )
        }
    }
    return AiVideoFrameSampling(
        strategy = optString("strategy"),
        selectedFrames = selectedFrames,
    )
}

private fun JSONArray?.toAiTagItems(): List<AiTagItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiTagItem>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiTagItem(
            tagId = item.optString("tag_id", item.optString("tagId")),
            score = item.optDouble("score", 0.0),
            source = item.optString("source", "llm"),
        )
    }
    return result
}

private fun JSONArray?.toAiVideoSegments(): List<AiVideoSegment> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiVideoSegment>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiVideoSegment(
            startMs = item.optLong("start_ms"),
            endMs = item.optLong("end_ms"),
            scene = item.optString("scene"),
            characters = item.optJSONArray("characters").toStringList(),
            visualEvents = item.optJSONArray("visual_events").toStringList(),
            dialogueSummary = item.optString("dialogue_summary"),
            interactionSuggestion = item.optString("interaction_suggestion"),
        )
    }
    return result
}

private fun JSONArray?.toAiVideoCharacters(): List<AiVideoCharacter> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiVideoCharacter>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiVideoCharacter(
            name = item.optString("name"),
            traits = item.optJSONArray("traits").toStringList(),
        )
    }
    return result
}

private fun JSONArray?.toAiVideoInteractionCandidates(): List<AiVideoInteractionCandidate> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiVideoInteractionCandidate>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiVideoInteractionCandidate(
            timeMs = item.optLong("time_ms"),
            type = item.optString("type"),
            question = item.optString("question"),
            reason = item.optString("reason"),
            options = item.optJSONArray("options").toStringList(),
        )
    }
    return result
}

private fun JSONArray?.toAiVideoScreenTextCues(): List<AiVideoScreenTextCue> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiVideoScreenTextCue>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiVideoScreenTextCue(
            timeMs = item.optLong("time_ms"),
            text = item.optString("text"),
            cueType = item.optString("cue_type"),
            reason = item.optString("reason"),
        )
    }
    return result
}

private fun JSONObject?.toAiVideoAudioText(): AiVideoAudioText {
    if (this == null) {
        return AiVideoAudioText(status = "unavailable", transcript = "", source = "")
    }
    return AiVideoAudioText(
        status = optString("status", "unavailable"),
        transcript = optString("transcript"),
        source = optString("source"),
    )
}

private fun JSONArray?.toAiCharacterPerspectives(): List<AiCharacterPerspective> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiCharacterPerspective>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiCharacterPerspective(
            name = item.optString("name"),
            question = item.optString("question"),
        )
    }
    return result
}

private fun JSONArray?.toAiHistoryRecapItems(): List<AiHistoryRecapItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiHistoryRecapItem>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiHistoryRecapItem(
            episodeId = item.optString("episode_id"),
            episodeTitle = item.optString("episode_title"),
            progressText = item.optString("progress_text"),
            recap = item.optString("recap"),
            continueReason = item.optString("continue_reason"),
            suggestedAction = item.optString("suggested_action"),
        )
    }
    return result
}

private fun JSONArray?.toAiHomeRecommendItems(): List<AiHomeRecommendItem> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiHomeRecommendItem>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiHomeRecommendItem(
            dramaId = item.optString("drama_id"),
            title = item.optString("title"),
            rank = item.optInt("rank", index + 1),
            reason = item.optString("reason"),
            score = item.optDouble("score", 0.0),
            tags = item.optJSONArray("tags").toStringList(),
        )
    }
    return result
}

private fun JSONObject.toQualityEvaluationResult(): QualityEvaluationResult {
    val summary = optJSONObject("summary") ?: JSONObject()
    return QualityEvaluationResult(
        suiteVersion = optString("suiteVersion"),
        generatedAtMs = optLong("generatedAtMs"),
        source = optString("source"),
        summary = QualityEvaluationSummary(
            total = summary.optInt("total"),
            passed = summary.optInt("passed"),
            failed = summary.optInt("failed"),
            passRate = summary.optDouble("passRate"),
        ),
        checks = optJSONArray("checks").toQualityEvaluationChecks(),
    )
}

private fun JSONArray?.toQualityEvaluationChecks(): List<QualityEvaluationCheck> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<QualityEvaluationCheck>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += QualityEvaluationCheck(
            checkId = item.optString("checkId"),
            name = item.optString("name"),
            passed = item.optBoolean("passed"),
            severity = item.optString("severity"),
            detail = item.optString("detail"),
            targets = item.optJSONArray("targets").toStringList(),
        )
    }
    return result
}

private fun JSONArray?.toAiProfileTagUpdates(): List<AiProfileTagUpdate> {
    if (this == null) {
        return emptyList()
    }
    val result = mutableListOf<AiProfileTagUpdate>()
    for (index in 0 until length()) {
        val item = optJSONObject(index) ?: continue
        result += AiProfileTagUpdate(
            tagId = item.optString("tag_id", item.optString("tagId")),
            delta = item.optDouble("delta", 0.0),
            source = item.optString("source", "llm"),
        )
    }
    return result
}
