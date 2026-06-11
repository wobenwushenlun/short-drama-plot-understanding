package com.shortdrama.plotunderstanding.feature.home

data class CheckinCardStyleOption(
    val id: String,
    val label: String,
)

val CHECKIN_CARD_STYLE_OPTIONS = listOf(
    CheckinCardStyleOption("short_drama_poster", "短剧通用"),
    CheckinCardStyleOption("family_glory", "家族荣耀"),
    CheckinCardStyleOption("face_slap", "打脸爽点"),
    CheckinCardStyleOption("identity_reveal", "身份揭露"),
    CheckinCardStyleOption("reversal_scene", "反转名场面"),
)

data class CoverPalette(
    val primary: String = "#25130F",
    val secondary: String = "#8A4F22",
    val accent: String = "#F8D36D",
)

data class CoverVisualLayers(
    val portraitUrl: String = "",
    val identityLabel: String = "身份反转",
    val heatLabel: String = "178.8万人想看",
    val latestLabel: String = "",
    val shareHint: String = "生成同款打卡图",
)

data class CoverVisualMetadata(
    val style: String = "family_reversal_poster",
    val badge: String = "高能逆袭",
    val hook: String = "十八岁外表，太奶奶气场回归纪家",
    val palette: CoverPalette = CoverPalette(),
    val layers: CoverVisualLayers = CoverVisualLayers(),
)

data class HomeDramaCard(
    val dramaId: String,
    val title: String,
    val coverUrl: String,
    val coverVisual: CoverVisualMetadata = CoverVisualMetadata(),
    val description: String,
    val tags: List<String>,
    val latestEpisodeNo: Int,
    val interactionHint: String,
    val recommendReason: String,
    val playUrl: String,
    val contentSource: String,
)

data class DramaDetailModel(
    val dramaId: String,
    val title: String,
    val coverUrl: String,
    val coverVisual: CoverVisualMetadata = CoverVisualMetadata(),
    val description: String,
    val tags: List<String>,
    val characters: List<DramaCharacter>,
    val latestEpisodeNo: Int,
    val interactionHint: String,
)

data class DramaCharacter(
    val characterId: String,
    val name: String,
    val avatarUrl: String,
)

data class EpisodeCard(
    val episodeId: String,
    val episodeNo: Int,
    val title: String,
    val durationMs: Long,
    val summary: String,
    val playUrl: String,
)

data class StorySummaryEpisode(
    val episodeId: String,
    val episodeNo: Int,
    val summary: String,
)

data class StorySummaryCacheAttempt(
    val source: String,
    val status: String,
    val generatedAtMs: Long,
    val modelName: String,
    val latencyMs: Long,
    val degradeReason: String,
)

data class StorySummaryCacheStatus(
    val dramaId: String,
    val promptVersion: String,
    val source: String,
    val status: String,
    val generatedAtMs: Long,
    val modelName: String,
    val latencyMs: Long,
    val degradeReason: String,
    val dramaDescription: String,
    val episodes: List<StorySummaryEpisode>,
    val latestAttempt: StorySummaryCacheAttempt,
)

data class ShareableMoment(
    val momentId: String,
    val dramaId: String,
    val episodeId: String,
    val episodeNo: Int,
    val episodeTitle: String,
    val startMs: Long,
    val endMs: Long,
    val title: String,
    val hookText: String,
    val sourceNodeId: String,
    val source: String,
    val selectionStrategy: String = "",
    val heatScore: Int,
    val playUrl: String,
    val savedAtMs: Long = 0L,
)

data class DemoRoutePlan(
    val routeId: String,
    val dramaId: String,
    val title: String,
    val source: String,
    val entry: DemoRouteEntry,
    val steps: List<DemoRouteStep>,
    val checks: DemoRouteChecks,
)

data class DemoRouteEntry(
    val episodeId: String,
    val startMs: Long,
    val momentId: String,
    val title: String,
)

data class DemoRouteStep(
    val stepId: String,
    val order: Int,
    val title: String,
    val description: String,
    val actionType: String,
    val api: String,
    val status: String,
    val episodeId: String,
    val startMs: Long,
    val evidenceCount: Int,
)

data class DemoRouteChecks(
    val usesFakeData: Boolean,
    val restartSafe: Boolean,
    val homeFallbackAvailable: Boolean,
    val sqliteBacked: Boolean,
    val evidenceGraphAvailable: Boolean,
)

data class DefenseDemoModeStatus(
    val enabled: Boolean,
    val routeId: String,
    val dramaId: String,
    val title: String,
    val description: String,
    val fixedStrategy: String,
    val contentSource: String,
    val entry: DemoRouteEntry,
    val quickSteps: List<DefenseDemoQuickStep>,
    val fallbacks: DefenseDemoFallbacks,
)

data class DefenseDemoQuickStep(
    val stepId: String,
    val title: String,
    val actionType: String,
    val status: String,
    val api: String,
)

data class DefenseDemoFallbacks(
    val homeFallbackAvailable: Boolean,
    val sqliteBacked: Boolean,
    val evidenceGraphAvailable: Boolean,
    val lastSuccessArtifactAvailable: Boolean,
)

data class PlaybackEpisode(
    val episodeId: String,
    val title: String,
    val playUrl: String,
    val hlsUrl: String,
    val hlsAvailable: Boolean,
    val preferredPlayUrl: String,
    val expireAtMs: Long,
)

data class InteractionConfig(
    val dramaId: String,
    val episodeId: String,
    val nodes: List<InteractionNode>,
    val timelineItems: List<InteractionTimelineItem> = emptyList(),
    val timedEvents: List<InteractionTimedEvent> = emptyList(),
    val generationPipeline: InteractionGenerationPipeline? = null,
    val evidenceGraph: EvidenceGraph? = null,
)

data class InteractionGenerationPipeline(
    val mode: String,
    val sourceStatus: String,
    val evidenceSources: List<String>,
    val candidateNodeCount: Int,
    val confirmedNodeCount: Int,
    val timelineItemCount: Int,
)

data class InteractionTimelineItem(
    val itemId: String,
    val type: String,
    val track: String,
    val startMs: Long,
    val endMs: Long,
    val analyticsKey: String,
)

data class InteractionSafeArea(
    val topDp: Int = 24,
    val bottomDp: Int = 24,
    val startDp: Int = 16,
    val endDp: Int = 16,
    val avoidRightRail: Boolean = false,
    val avoidDanmaku: Boolean = false,
    val avoidProgressBar: Boolean = false,
)

data class InteractionTimedEvent(
    val eventId: String,
    val episodeId: String,
    val startMs: Long,
    val endMs: Long,
    val componentType: String,
    val visualStyle: String,
    val placement: String,
    val safeArea: InteractionSafeArea,
    val maxLines: Int,
    val analyticsKey: String,
    val evidenceRefs: List<String>,
    val generationSource: String,
    val confidence: Double,
    val reviewStatus: String,
    val payloadHash: String,
)

data class EvidenceGraph(
    val episodeId: String,
    val focusTimeMs: Long,
    val sourceStatus: String,
    val evidenceSources: List<String>,
    val storyFacets: EvidenceStoryFacets = EvidenceStoryFacets(),
    val explanations: List<EvidenceGraphExplanation> = emptyList(),
    val nodes: List<EvidenceGraphNode>,
    val evidence: List<EvidenceGraphItem>,
    val relations: List<EvidenceGraphRelation>,
)

data class EvidenceStoryFacets(
    val characters: List<String> = emptyList(),
    val conflicts: List<String> = emptyList(),
    val reversals: List<String> = emptyList(),
    val audienceResonance: List<String> = emptyList(),
)

data class EvidenceGraphExplanation(
    val nodeId: String,
    val title: String,
    val storyTags: List<String>,
    val audienceResonance: String,
    val evidenceSummary: String,
    val explainText: String,
    val confidence: Double,
)

data class EvidenceGraphNode(
    val nodeId: String,
    val eventId: String,
    val title: String,
    val timeMs: Long,
    val endMs: Long,
    val componentType: String,
    val generationSource: String,
    val reviewStatus: String,
    val confidence: Double,
    val evidenceRefs: List<String>,
    val resolvedEvidenceRefs: List<String>,
    val whyText: String,
)

data class EvidenceGraphItem(
    val refId: String,
    val kind: String,
    val sourceLabel: String,
    val timeMs: Long,
    val endMs: Long,
    val displayText: String,
    val assetPath: String,
)

data class EvidenceGraphRelation(
    val fromNodeId: String,
    val toEvidenceRef: String,
    val relationType: String,
    val timeDeltaMs: Long,
)

data class InteractionCandidateNode(
    val candidateId: String,
    val timeMs: Long,
    val type: String,
    val question: String,
    val reason: String,
    val options: List<String>,
    val source: String,
    val evidenceRefs: List<String>,
    val confidence: Double,
    val reviewStatus: String,
    val orchestrationAdvice: InteractionCandidateOrchestrationAdvice = InteractionCandidateOrchestrationAdvice(),
)

data class InteractionCandidateOrchestrationAdvice(
    val recommendedComponentType: String = "",
    val visualStyle: String = "",
    val placement: String = "",
    val safeArea: InteractionSafeArea = InteractionSafeArea(),
    val maxLines: Int = 2,
    val analyticsKey: String = "",
    val evidenceSummary: String = "",
    val publishEligible: Boolean = false,
)

data class InteractionCandidateReviewResult(
    val candidateId: String,
    val episodeId: String,
    val reviewStatus: String,
    val editedQuestion: String,
    val editedOptions: List<String>,
    val reviewNote: String,
    val reviewedAtMs: Long,
)

data class DanmakuEmotionReport(
    val episodeId: String,
    val episodeNo: Int,
    val source: String,
    val summary: String,
    val items: List<DanmakuEmotionPoint>,
)

data class DanmakuEmotionPoint(
    val hotspotId: String,
    val episodeId: String,
    val timeMs: Long,
    val startMs: Long,
    val endMs: Long,
    val keywords: List<String>,
    val emotion: String,
    val emotionScore: Double,
    val commentIntensity: Int,
    val likeIntensity: Int,
    val heatScore: Int,
    val suggestedInteraction: String,
    val suggestedComponentType: String,
    val sceneSummary: String,
    val evidenceRefs: List<String>,
    val reviewStatus: String,
)

data class InteractionNode(
    val id: String,
    val type: String,
    val title: String,
    val subtitle: String,
    val triggerMs: Long,
    val displayMode: String,
    val timeoutMs: Long,
    val allowSkip: Boolean,
    val skipText: String,
    val componentType: String,
    val analyticsKey: String,
    val placement: String,
    val safeArea: InteractionSafeArea,
    val maxLines: Int,
    val visualStyle: String,
    val effectText: String,
    val badgeText: String,
    val promptText: String,
    val aiInsertTitle: String,
    val aiInsertDescription: String,
    val aiInsertMediaUrl: String,
    val aiInsertMediaType: String,
    val aiInsertHighEnergyLine: String,
    val aiInsertProviderName: String,
    val options: List<InteractionOption>,
    val evidenceRefs: List<String> = emptyList(),
    val generationSource: String = "manual",
    val confidence: Double = 0.0,
    val reviewStatus: String = "",
)

data class InteractionOption(
    val id: String,
    val text: String,
    val branch: InteractionBranch? = null,
)

data class InteractionBranch(
    val segmentId: String,
    val startMs: Long,
    val endMs: Long,
    val returnSeekMs: Long,
    val mediaUrl: String = "",
    val mediaType: String = "",
    val playbackMode: String = "REPLACE_MAIN",
)

data class InteractionSubmitResult(
    val recordId: String,
    val feedbackText: String,
    val rewardText: String,
    val nextActionType: String,
    val aggregate: Map<String, Int>,
)

data class InteractionInsights(
    val episodeId: String,
    val durationMs: Long,
    val totalInteractions: Int,
    val nodeCount: Int,
    val peakNodeId: String,
    val peakNodeTitle: String,
    val crowdSummary: String,
    val nodes: List<InteractionHeatNode>,
)

data class InteractionHeatNode(
    val nodeId: String,
    val title: String,
    val style: String,
    val effectText: String,
    val badgeText: String,
    val triggerMs: Long,
    val heatScore: Int,
    val totalCount: Int,
    val liveCount: Int,
    val options: List<InteractionOptionStat>,
)

data class InteractionOptionStat(
    val optionId: String,
    val optionText: String,
    val count: Int,
    val liveCount: Int,
    val percent: Int,
)

data class WatchHistoryItem(
    val dramaId: String,
    val dramaTitle: String,
    val episodeId: String,
    val episodeTitle: String,
    val playUrl: String,
    val lastProgressMs: Long,
    val durationMs: Long,
    val isCompleted: Boolean,
    val updatedAtMs: Long,
)

data class TelemetryEvent(
    val eventId: String,
    val eventName: String,
    val screenName: String,
    val dramaId: String? = null,
    val episodeId: String? = null,
    val nodeId: String? = null,
    val progressMs: Long? = null,
    val clientTsMs: Long,
    val properties: Map<String, String> = emptyMap(),
)

data class TelemetryDispatchResult(
    val acceptedIds: List<String>,
    val retryableIds: List<String>,
)

data class AiTagItem(
    val tagId: String,
    val score: Double,
    val source: String,
)

data class AiProfileTagUpdate(
    val tagId: String,
    val delta: Double,
    val source: String,
)

data class AiArtifactMeta(
    val source: String = "",
    val version: Int = 0,
    val restoredFromLastSuccess: Boolean = false,
    val lastSuccessVersion: Int = 0,
    val lastSuccessSource: String = "",
    val lastSuccessAtMs: Long = 0L,
)

data class AiContentRecapResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val summary: String,
    val highlights: List<String>,
    val characterFocus: List<String>,
    val discussionSeeds: List<String>,
    val continueReason: String,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class AiInteractionFeedbackResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val feedbackText: String,
    val selectionExplanation: String,
    val followupQuestion: String,
    val derivedTags: List<AiTagItem>,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class AiTagExtractResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val contentTags: List<AiTagItem>,
    val interactionTags: List<AiTagItem>,
    val userProfileTagUpdates: List<AiProfileTagUpdate>,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class AiModerationResult(
    val status: String,
    val decision: String,
    val riskFlags: List<String>,
    val matchedKeywords: List<String>,
    val reviewText: String,
    val blockReason: String? = null,
)

data class AiCharacterPerspective(
    val name: String,
    val question: String,
)

data class AiDiscussionSeedResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val discussionQuestions: List<String>,
    val characterPerspectives: List<AiCharacterPerspective>,
    val nextEpisodePredictions: List<String>,
    val alternateChoiceTopics: List<String>,
    val shareText: String,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class GeneratedMediaAsset(
    val assetId: String = "",
    val remoteUrl: String = "",
    val localUrl: String = "",
    val mediaUrl: String = "",
    val contentType: String = "",
    val cacheStatus: String = "",
    val byteSize: Long = 0L,
    val degradeReason: String = "",
)

data class AiStoryContinuationResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val episodeId: String,
    val title: String,
    val summary: String,
    val sceneDirection: String,
    val dialogueLines: List<String>,
    val viewerHook: String,
    val mediaUrl: String,
    val mediaType: String,
    val providerName: String,
    val providerMode: String,
    val remoteAttemptStatus: String,
    val remoteAttemptReason: String,
    val referenceStatus: String,
    val playbackMode: String,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
    val mediaAsset: GeneratedMediaAsset = GeneratedMediaAsset(),
)

data class AgnesStatusResult(
    val configured: Boolean,
    val source: String,
    val baseUrl: String,
    val imageModel: String,
    val videoModel: String,
)

data class AiCheckinCardResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val title: String,
    val prompt: String,
    val imageUrl: String,
    val provider: String,
    val style: String,
    val styleLabel: String,
    val episodeId: String,
    val momentId: String,
    val cardStatus: String,
    val cardLatencyMs: Long,
    val cardDegradeReason: String,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
    val remoteImageUrl: String = "",
    val mediaAsset: GeneratedMediaAsset = GeneratedMediaAsset(),
)

data class GenerationTaskLastSuccess(
    val taskId: String,
    val mediaUrl: String,
    val mediaType: String,
    val provider: String,
    val updatedAtMs: Long,
    val mediaAsset: GeneratedMediaAsset = GeneratedMediaAsset(),
)

data class GenerationTaskResult(
    val taskId: String,
    val taskType: String,
    val dramaId: String,
    val episodeId: String,
    val status: String,
    val provider: String,
    val modelName: String,
    val mediaUrl: String,
    val mediaType: String,
    val latencyMs: Long,
    val degradeReason: String,
    val resultTitle: String,
    val providerMode: String,
    val createdAtMs: Long,
    val updatedAtMs: Long,
    val lastSuccess: GenerationTaskLastSuccess,
    val mediaAsset: GeneratedMediaAsset = GeneratedMediaAsset(),
)

data class GeneratedAssetManagementResult(
    val dramaId: String,
    val summary: GeneratedAssetManagementSummary,
    val recentSuccesses: List<GeneratedAssetManagementItem>,
    val failedAttempts: List<GeneratedAssetManagementItem>,
)

data class GeneratedAssetManagementSummary(
    val successCount: Int,
    val failedCount: Int,
    val cachedByteSize: Long,
    val source: String,
)

data class GeneratedAssetManagementItem(
    val taskId: String,
    val taskType: String,
    val dramaId: String,
    val episodeId: String,
    val status: String,
    val provider: String,
    val modelName: String,
    val mediaUrl: String,
    val mediaType: String,
    val latencyMs: Long,
    val degradeReason: String,
    val title: String,
    val updatedAtMs: Long,
    val mediaAsset: GeneratedMediaAsset = GeneratedMediaAsset(),
)

data class GeneratedAssetCleanupResult(
    val dramaId: String,
    val deletedCount: Int,
    val statuses: List<String>,
)

data class AiHistoryRecapItem(
    val episodeId: String,
    val episodeTitle: String,
    val progressText: String,
    val recap: String,
    val continueReason: String,
    val suggestedAction: String,
)

data class AiHistoryRecapResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val items: List<AiHistoryRecapItem>,
    val summary: String,
    val nextEpisodeId: String,
    val continueReason: String,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class AiHomeRecommendItem(
    val dramaId: String,
    val title: String,
    val rank: Int,
    val reason: String,
    val score: Double,
    val tags: List<String>,
)

data class AiHomeRecommendResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val items: List<AiHomeRecommendItem>,
    val strategy: String,
    val personalizationSignals: List<String>,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)

data class OperationsDashboardResult(
    val storage: OperationsDashboardStorage,
    val dramaId: String,
    val episodeId: String,
    val generatedAtMs: Long,
    val overview: OperationsDashboardOverview,
    val trend: List<OperationsDashboardTrendPoint>,
    val trendSummary: OperationsDashboardTrendSummary,
    val hotNodes: List<OperationsDashboardHotNode>,
    val ai: OperationsDashboardAiSummary,
    val highlightStrategies: List<OperationsDashboardHighlightStrategy>,
    val agnesGeneration: OperationsDashboardAgnesGeneration,
    val profile: OperationsDashboardProfileSummary,
)

data class OperationsDashboardStorage(
    val engine: String,
    val persistent: Boolean,
)

data class OperationsDashboardOverview(
    val interactionCtr: Double,
    val interactionImpressions: Int,
    val interactionSubmits: Int,
    val interactionCount: Int,
    val insertPlaybackCompletionRate: Double,
    val insertPlaybackStarts: Int,
    val insertPlaybackCompleted: Int,
    val aiSuccessRate: Double,
    val aiDegradedRate: Double,
    val aiP95LatencyMs: Long,
    val watchEpisodeCount: Int,
    val watchCompletedCount: Int,
    val videoStartAttempts: Int,
    val firstFrameRendered: Int,
    val startupSuccessRate: Double,
    val startupFailureRate: Double,
    val exitBeforeStartCount: Int,
    val rebufferCount: Int,
    val rebufferTotalMs: Long,
    val startupP50Ms: Long,
    val startupP95Ms: Long,
    val rebufferP95Ms: Long,
    val savedMomentCount: Int,
    val eventCount: Int,
)

data class OperationsDashboardTrendPoint(
    val day: String,
    val label: String,
    val interactionImpressions: Int,
    val interactionSubmits: Int,
    val interactionCtr: Double,
    val watchEpisodeCount: Int,
    val watchCompletedCount: Int,
    val watchCompletionRate: Double,
    val insertPlaybackStarts: Int,
    val insertPlaybackCompleted: Int,
    val insertPlaybackCompletionRate: Double,
    val videoStartAttempts: Int,
    val firstFrameRendered: Int,
    val startupSuccessRate: Double,
    val startupFailureRate: Double,
    val exitBeforeStartCount: Int,
    val rebufferCount: Int,
    val rebufferTotalMs: Long,
    val startupP95Ms: Long,
    val rebufferP95Ms: Long,
    val playbackErrorCount: Int,
    val fullscreenExitCount: Int,
    val continueWatchCount: Int,
    val aiAttemptCount: Int,
    val aiSuccessCount: Int,
    val aiDegradedCount: Int,
    val aiBlockedCount: Int,
    val aiSuccessRate: Double,
    val aiDegradedRate: Double,
    val aiP95LatencyMs: Long,
)

data class OperationsDashboardTrendSummary(
    val activeDayCount: Int,
    val bestCtrDay: String,
    val bestCtr: Double,
    val bestStrategy: String,
    val bestStrategyLabel: String,
    val bestStrategyCtr: Double,
    val qualityStatus: String,
    val riskNotes: List<String>,
)

data class OperationsDashboardHotNode(
    val nodeId: String,
    val nodeTitle: String,
    val impressions: Int,
    val submits: Int,
    val ctr: Double,
    val choices: List<OperationsDashboardChoice>,
)

data class OperationsDashboardChoice(
    val optionId: String,
    val optionText: String,
    val selects: Int,
)

data class OperationsDashboardAiSummary(
    val total: Int,
    val successCount: Int,
    val degradedCount: Int,
    val blockedCount: Int,
    val successRate: Double,
    val degradedRate: Double,
    val p95LatencyMs: Long,
    val capabilities: List<OperationsDashboardAiCapability>,
)

data class OperationsDashboardAiCapability(
    val capability: String,
    val total: Int,
    val successCount: Int,
    val degradedCount: Int,
    val blockedCount: Int,
    val successRate: Double,
    val degradedRate: Double,
    val p95LatencyMs: Long,
    val latestAtMs: Long,
)

data class OperationsDashboardAgnesGeneration(
    val totalStarts: Int,
    val totalSuccess: Int,
    val totalDegraded: Int,
    val successRate: Double,
    val degradedRate: Double,
    val p95LatencyMs: Long,
    val localTemplateFallbackCount: Int,
    val latestAtMs: Long,
    val image: OperationsDashboardAgnesBucket,
    val video: OperationsDashboardAgnesBucket,
)

data class OperationsDashboardAgnesBucket(
    val starts: Int,
    val success: Int,
    val degraded: Int,
    val successRate: Double,
    val degradedRate: Double,
    val p95LatencyMs: Long,
)

data class OperationsDashboardHighlightStrategy(
    val selectionStrategy: String,
    val label: String,
    val impressions: Int,
    val clicks: Int,
    val ctr: Double,
    val jumps: Int,
    val jumpRate: Double,
    val playCompleted: Int,
    val completionRate: Double,
    val saved: Int,
    val saveRate: Double,
    val averageRank: Double,
    val averageHeatScore: Double,
    val uniqueMomentCount: Int,
    val latestAtMs: Long,
)

data class OperationsDashboardProfileSummary(
    val interestTags: List<String>,
    val interestTagDistribution: List<OperationsDashboardTagDistribution>,
    val recommendReason: String,
    val topNodes: List<OperationsDashboardTopNode>,
)

data class OperationsDashboardTagDistribution(
    val tag: String,
    val count: Int,
)

data class OperationsDashboardTopNode(
    val nodeId: String,
    val nodeTitle: String,
    val submits: Int,
)

data class QualityEvaluationResult(
    val suiteVersion: String,
    val generatedAtMs: Long,
    val source: String,
    val summary: QualityEvaluationSummary,
    val checks: List<QualityEvaluationCheck>,
)

data class QualityEvaluationSummary(
    val total: Int,
    val passed: Int,
    val failed: Int,
    val passRate: Double,
)

data class QualityEvaluationCheck(
    val checkId: String,
    val name: String,
    val passed: Boolean,
    val severity: String,
    val detail: String,
    val targets: List<String> = emptyList(),
)

data class AiVideoSegment(
    val startMs: Long,
    val endMs: Long,
    val scene: String,
    val characters: List<String>,
    val visualEvents: List<String>,
    val dialogueSummary: String,
    val interactionSuggestion: String,
)

data class AiVideoCharacter(
    val name: String,
    val traits: List<String>,
)

data class AiVideoInteractionCandidate(
    val timeMs: Long,
    val type: String,
    val question: String,
    val reason: String,
    val options: List<String>,
)

data class AiVideoScreenTextCue(
    val timeMs: Long,
    val text: String,
    val cueType: String,
    val reason: String,
)

data class AiVideoAudioText(
    val status: String,
    val transcript: String,
    val source: String,
)

data class AiVideoFrameSample(
    val timeMs: Long,
    val source: String,
    val reason: String,
    val score: Double,
)

data class AiVideoFrameSampling(
    val strategy: String,
    val selectedFrames: List<AiVideoFrameSample>,
)

data class AiVideoUnderstandingResult(
    val status: String,
    val cached: Boolean,
    val latencyMs: Long,
    val modelName: String,
    val episodeId: String,
    val summary: String,
    val segments: List<AiVideoSegment>,
    val characters: List<AiVideoCharacter>,
    val interactionCandidates: List<AiVideoInteractionCandidate>,
    val evidence: List<String>,
    val productionNotes: List<String>,
    val screenTextCues: List<AiVideoScreenTextCue>,
    val audioText: AiVideoAudioText,
    val frameSampling: AiVideoFrameSampling,
    val artifact: AiArtifactMeta = AiArtifactMeta(),
    val degradeReason: String? = null,
)
