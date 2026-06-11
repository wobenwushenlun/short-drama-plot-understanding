@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.contest.aigc.shortplay.feature.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.contest.aigc.shortplay.core.ui.AigcModeToggle
import com.contest.aigc.shortplay.core.ui.AigcScreenScaffold
import com.contest.aigc.shortplay.core.ui.AigcThemeMode
import kotlinx.coroutines.launch

private sealed interface AiCallState<out T> {
    data object Idle : AiCallState<Nothing>
    data object Loading : AiCallState<Nothing>
    data class Success<T>(val data: T) : AiCallState<T>
    data class Error(val message: String) : AiCallState<Nothing>
}
@Composable
fun AiExperienceRoute(
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onBack: () -> Unit,
    onOpenEpisode: (String, Long) -> Unit = { _, _ -> },
    repository: ShortPlayRepository? = null,
) {
    val resolvedRepository = repository ?: rememberRepository()
    val scope = rememberCoroutineScope()
    var episodeId by rememberSaveable { mutableStateOf("tainai3_ep01") }
    var dramaId by rememberSaveable { mutableStateOf("tainai3") }
    var moderationText by rememberSaveable { mutableStateOf("如果是你，你会怎么选？") }
    var selectedNodeId by rememberSaveable { mutableStateOf("") }
    var selectedOptionId by rememberSaveable { mutableStateOf("") }
    var interactionRefreshTick by remember { mutableStateOf(0) }
    var candidateRefreshTick by remember { mutableStateOf(0) }
    var recapState by remember { mutableStateOf<AiCallState<AiContentRecapResult>>(AiCallState.Idle) }
    var feedbackState by remember { mutableStateOf<AiCallState<AiInteractionFeedbackResult>>(AiCallState.Idle) }
    var tagState by remember { mutableStateOf<AiCallState<AiTagExtractResult>>(AiCallState.Idle) }
    var moderationState by remember { mutableStateOf<AiCallState<AiModerationResult>>(AiCallState.Idle) }
    var discussionState by remember { mutableStateOf<AiCallState<AiDiscussionSeedResult>>(AiCallState.Idle) }
    var historyRecapState by remember { mutableStateOf<AiCallState<AiHistoryRecapResult>>(AiCallState.Idle) }
    var recommendState by remember { mutableStateOf<AiCallState<AiHomeRecommendResult>>(AiCallState.Idle) }
    var agnesStatusState by remember { mutableStateOf<AiCallState<AgnesStatusResult>>(AiCallState.Loading) }
    var agnesStoryState by remember { mutableStateOf<AiCallState<AiStoryContinuationResult>>(AiCallState.Idle) }
    var checkinCardState by remember { mutableStateOf<AiCallState<AiCheckinCardResult>>(AiCallState.Idle) }
    var generationTaskState by remember { mutableStateOf<AiCallState<GenerationTaskResult>>(AiCallState.Idle) }
    var generatedAssetState by remember { mutableStateOf<AiCallState<GeneratedAssetManagementResult>>(AiCallState.Loading) }
    var generatedAssetRefreshTick by remember { mutableStateOf(0) }
    var generatedAssetCleanupState by remember { mutableStateOf<AiCallState<GeneratedAssetCleanupResult>>(AiCallState.Idle) }
    var selectedCheckinStyle by rememberSaveable { mutableStateOf("short_drama_poster") }
    var operationsDashboardRefreshTick by remember { mutableStateOf(0) }
    var qualityEvaluationRefreshTick by remember { mutableStateOf(0) }
    var videoUnderstandingState by remember { mutableStateOf<AiCallState<AiVideoUnderstandingResult>>(AiCallState.Idle) }
    var storyCacheState by remember { mutableStateOf<AiCallState<StorySummaryCacheStatus>>(AiCallState.Loading) }
    var candidateReviewState by remember { mutableStateOf<AiCallState<InteractionCandidateReviewResult>>(AiCallState.Idle) }

    LaunchedEffect(dramaId, resolvedRepository) {
        storyCacheState = AiCallState.Loading
        storyCacheState = try {
            AiCallState.Success(resolvedRepository.loadStorySummaryCacheStatus(dramaId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "剧情简介缓存状态加载失败")
        }
    }

    LaunchedEffect(resolvedRepository) {
        agnesStatusState = AiCallState.Loading
        agnesStatusState = try {
            AiCallState.Success(resolvedRepository.loadAgnesStatus())
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "Agnes 状态加载失败")
        }
    }

    LaunchedEffect(dramaId, generatedAssetRefreshTick, resolvedRepository) {
        generatedAssetState = AiCallState.Loading
        generatedAssetState = try {
            AiCallState.Success(resolvedRepository.loadGeneratedAssetManagement(dramaId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "生成产物管理加载失败")
        }
    }

    val interactionState by produceState<AiCallState<InteractionConfig>>(
        initialValue = AiCallState.Loading,
        episodeId,
        interactionRefreshTick,
        resolvedRepository
    ) {
        value = try {
            AiCallState.Success(resolvedRepository.loadInteractionConfig(episodeId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "互动配置加载失败")
        }
    }

    val candidateState by produceState<AiCallState<List<InteractionCandidateNode>>>(
        initialValue = AiCallState.Loading,
        episodeId,
        candidateRefreshTick,
        resolvedRepository
    ) {
        value = try {
            AiCallState.Success(resolvedRepository.loadInteractionCandidates(episodeId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "候选节点加载失败")
        }
    }

    val danmakuEmotionState by produceState<AiCallState<DanmakuEmotionReport>>(
        initialValue = AiCallState.Loading,
        episodeId,
        candidateRefreshTick,
        resolvedRepository
    ) {
        value = try {
            AiCallState.Success(resolvedRepository.loadDanmakuEmotionReport(episodeId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "观众共鸣点加载失败")
        }
    }

    val operationsDashboardState by produceState<AiCallState<OperationsDashboardResult>>(
        initialValue = AiCallState.Loading,
        episodeId,
        operationsDashboardRefreshTick,
        resolvedRepository
    ) {
        value = try {
            AiCallState.Success(resolvedRepository.loadOperationsDashboard(episodeId))
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "运营看板加载失败")
        }
    }

    val qualityEvaluationState by produceState<AiCallState<QualityEvaluationResult>>(
        initialValue = AiCallState.Loading,
        qualityEvaluationRefreshTick,
        resolvedRepository
    ) {
        value = try {
            AiCallState.Success(resolvedRepository.loadQualityEvaluation())
        } catch (throwable: Throwable) {
            AiCallState.Error(throwable.message ?: "质量评测报告加载失败")
        }
    }

    LaunchedEffect(interactionState) {
        val config = (interactionState as? AiCallState.Success<*>)?.data as? InteractionConfig
            ?: return@LaunchedEffect
        val defaultNode = config.nodes.firstOrNull() ?: return@LaunchedEffect
        if (selectedNodeId.isBlank() || config.nodes.none { it.id == selectedNodeId }) {
            selectedNodeId = defaultNode.id
        }
        val resolvedNode = config.nodes.firstOrNull { it.id == selectedNodeId } ?: defaultNode
        if (selectedOptionId.isBlank() || resolvedNode.options.none { it.id == selectedOptionId }) {
            selectedOptionId = resolvedNode.options.firstOrNull()?.id.orEmpty()
        }
    }

    val currentConfig = (interactionState as? AiCallState.Success<*>)?.data as? InteractionConfig
    val selectedNode = currentConfig?.nodes?.firstOrNull { it.id == selectedNodeId }
        ?: currentConfig?.nodes?.firstOrNull()
    val selectedOption = selectedNode?.options?.firstOrNull { it.id == selectedOptionId }
        ?: selectedNode?.options?.firstOrNull()

    AigcScreenScaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    scrolledContainerColor = Color.Transparent,
                ),
                title = { Text(text = "AI体验") },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text(text = "返回")
                    }
                },
                actions = {
                    AigcModeToggle(
                        themeMode = themeMode,
                        onToggle = onToggleTheme,
                        modifier = Modifier.padding(end = 12.dp),
                    )
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                AiEpisodePanel(
                    episodeId = episodeId,
                    dramaId = dramaId,
                    onEpisodeIdChange = { episodeId = it.trim() },
                    onDramaIdChange = { dramaId = it.trim() },
                    onRefresh = {
                        interactionRefreshTick += 1
                        candidateRefreshTick += 1
                    }
                )
            }
            item {
                AiInteractionPanel(
                    state = interactionState,
                    selectedNodeId = selectedNodeId,
                    selectedOptionId = selectedOptionId,
                    onSelectNode = { node ->
                        selectedNodeId = node.id
                        selectedOptionId = node.options.firstOrNull()?.id.orEmpty()
                    },
                    onSelectOption = { option ->
                        selectedOptionId = option.id
                    }
                )
            }
            item {
                AiInteractionComponentPreviewPanel(state = interactionState)
            }
            item {
                AiCandidateReviewPanel(
                    state = candidateState,
                    reviewState = candidateReviewState,
                    onReview = { candidate, reviewStatus ->
                        scope.launch {
                            candidateReviewState = AiCallState.Loading
                            candidateReviewState = try {
                                val editedQuestion = if (reviewStatus == "edited") {
                                    candidate.question.ifBlank { "这个爽点你会怎么选" }.let { text ->
                                        if (text.endsWith("？")) text else "$text？"
                                    }
                                } else {
                                    ""
                                }
                                val editedOptions = if (reviewStatus == "edited") {
                                    candidate.options.take(3).ifEmpty { listOf("立刻反击", "继续观察", "支持主角") }
                                } else {
                                    emptyList()
                                }
                                AiCallState.Success(
                                    resolvedRepository.reviewInteractionCandidate(
                                        episodeId = episodeId,
                                        candidateId = candidate.candidateId,
                                        reviewStatus = reviewStatus,
                                        editedQuestion = editedQuestion,
                                        editedOptions = editedOptions,
                                        reviewNote = when (reviewStatus) {
                                            "accepted" -> "Android 审核接受"
                                            "rejected" -> "Android 审核拒绝"
                                            else -> "Android 轻量编辑后接受"
                                        },
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "候选节点审核失败")
                            }
                            candidateRefreshTick += 1
                            interactionRefreshTick += 1
                        }
                    }
                )
            }
            item {
                AiDanmakuEmotionPanel(
                    state = danmakuEmotionState,
                    onOpenPoint = { point ->
                        onOpenEpisode(point.episodeId.ifBlank { episodeId }, point.timeMs)
                    }
                )
            }
            item {
                AiStorySummaryCachePanel(
                    state = storyCacheState,
                    onRefresh = {
                        scope.launch {
                            storyCacheState = AiCallState.Loading
                            storyCacheState = try {
                                AiCallState.Success(resolvedRepository.refreshStorySummaryCache(dramaId))
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "刷新剧情简介缓存失败")
                            }
                        }
                    }
                )
            }
            item {
                AiRecapPanel(
                    state = recapState,
                    onGenerate = {
                        scope.launch {
                            recapState = AiCallState.Loading
                            recapState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiContentRecap(
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "生成摘要失败")
                            }
                        }
                    }
                )
            }
            item {
                AiVideoUnderstandingPanel(
                    state = videoUnderstandingState,
                    onGenerate = {
                        scope.launch {
                            videoUnderstandingState = AiCallState.Loading
                            videoUnderstandingState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiVideoUnderstanding(
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                        includeFrames = true,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "生成视频理解失败")
                            }
                        }
                    }
                )
            }
            item {
                AiAgnesGenerationPanel(
                    statusState = agnesStatusState,
                    storyState = agnesStoryState,
                    checkinState = checkinCardState,
                    taskState = generationTaskState,
                    generatedAssetState = generatedAssetState,
                    cleanupState = generatedAssetCleanupState,
                    selectedCheckinStyle = selectedCheckinStyle,
                    onCheckinStyleSelected = { selectedCheckinStyle = it },
                    onRefreshStatus = {
                        scope.launch {
                            agnesStatusState = AiCallState.Loading
                            agnesStatusState = try {
                                AiCallState.Success(resolvedRepository.loadAgnesStatus())
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "Agnes 状态加载失败")
                            }
                        }
                    },
                    onGenerateStory = {
                        scope.launch {
                            agnesStoryState = AiCallState.Loading
                            agnesStoryState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiStoryContinuation(
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "Agnes 续写视频生成失败")
                            }
                        }
                    },
                    onGenerateCheckin = {
                        scope.launch {
                            checkinCardState = AiCallState.Loading
                            checkinCardState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiCheckinCard(
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                        style = selectedCheckinStyle,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "Agnes 打卡图生成失败")
                            }
                        }
                    },
                    onCreateStoryTask = {
                        scope.launch {
                            generationTaskState = AiCallState.Loading
                            generationTaskState = try {
                                AiCallState.Success(
                                    resolvedRepository.createGenerationTask(
                                        taskType = "story_continuation_video",
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "续写视频任务创建失败")
                            }
                        }
                    },
                    onCreateCheckinTask = {
                        scope.launch {
                            generationTaskState = AiCallState.Loading
                            generationTaskState = try {
                                AiCallState.Success(
                                    resolvedRepository.createGenerationTask(
                                        taskType = "checkin_card",
                                        episodeId = episodeId,
                                        dramaId = dramaId,
                                        style = selectedCheckinStyle,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "打卡图任务创建失败")
                            }
                        }
                    },
                    onRefreshAssets = { generatedAssetRefreshTick += 1 },
                    onCleanupFailedAssets = {
                        scope.launch {
                            generatedAssetCleanupState = AiCallState.Loading
                            generatedAssetCleanupState = try {
                                val result = resolvedRepository.cleanupFailedGeneratedAssets(dramaId)
                                generatedAssetRefreshTick += 1
                                AiCallState.Success(result)
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "失败产物清理失败")
                            }
                        }
                    },
                )
            }
            item {
                AiFeedbackPanel(
                    state = feedbackState,
                    selectedNode = selectedNode,
                    selectedOption = selectedOption,
                    onGenerate = {
                        val node = selectedNode
                        val option = selectedOption
                        if (node == null || option == null) {
                            feedbackState = AiCallState.Error("请先选择互动节点和选项")
                        } else {
                            scope.launch {
                                feedbackState = AiCallState.Loading
                                feedbackState = try {
                                    AiCallState.Success(
                                        resolvedRepository.loadAiInteractionFeedback(
                                            episodeId = episodeId,
                                            nodeId = node.id,
                                            optionId = option.id,
                                            answerText = option.text,
                                            sceneSummary = node.subtitle,
                                            dramaId = dramaId,
                                        )
                                    )
                                } catch (throwable: Throwable) {
                                    AiCallState.Error(throwable.message ?: "生成反馈失败")
                                }
                            }
                        }
                    }
                )
            }
            item {
                AiTagPanel(
                    state = tagState,
                    selectedNode = selectedNode,
                    selectedOption = selectedOption,
                    onGenerate = {
                        val node = selectedNode
                        val option = selectedOption
                        if (node == null || option == null) {
                            tagState = AiCallState.Error("请先选择互动节点和选项")
                        } else {
                            scope.launch {
                                tagState = AiCallState.Loading
                                tagState = try {
                                    AiCallState.Success(
                                        resolvedRepository.loadAiTagExtract(
                                            episodeId = episodeId,
                                            nodeId = node.id,
                                            optionId = option.id,
                                            answerText = option.text,
                                            sceneSummary = node.subtitle,
                                            dramaId = dramaId,
                                        )
                                    )
                                } catch (throwable: Throwable) {
                                    AiCallState.Error(throwable.message ?: "抽取标签失败")
                                }
                            }
                        }
                    }
                )
            }
            item {
                AiModerationPanel(
                    text = moderationText,
                    state = moderationState,
                    onTextChange = { moderationText = it },
                    onGenerate = {
                        if (moderationText.isBlank()) {
                            moderationState = AiCallState.Error("请输入待审核文本")
                        } else {
                            scope.launch {
                                moderationState = AiCallState.Loading
                                moderationState = try {
                                    AiCallState.Success(
                                        resolvedRepository.loadAiModerationCheck(moderationText)
                                    )
                                } catch (throwable: Throwable) {
                                    AiCallState.Error(throwable.message ?: "内容审核失败")
                                }
                            }
                        }
                    }
                )
            }
            item {
                AiDiscussionPanel(
                    state = discussionState,
                    selectedNode = selectedNode,
                    selectedOption = selectedOption,
                    onGenerate = {
                        val node = selectedNode
                        val option = selectedOption
                        if (node == null || option == null) {
                            discussionState = AiCallState.Error("请先选择互动节点和选项")
                        } else {
                            scope.launch {
                                discussionState = AiCallState.Loading
                                discussionState = try {
                                    AiCallState.Success(
                                        resolvedRepository.loadAiDiscussionSeed(
                                            episodeId = episodeId,
                                            nodeId = node.id,
                                            optionId = option.id,
                                            selectionText = option.text,
                                            dramaId = dramaId,
                                        )
                                    )
                                } catch (throwable: Throwable) {
                                    AiCallState.Error(throwable.message ?: "生成讨论延展失败")
                                }
                            }
                        }
                    }
                )
            }
            item {
                AiHistoryRecapPanel(
                    state = historyRecapState,
                    onGenerate = {
                        scope.launch {
                            historyRecapState = AiCallState.Loading
                            historyRecapState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiHistoryRecap(
                                        size = 5,
                                        dramaId = dramaId,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "生成历史续播失败")
                            }
                        }
                    }
                )
            }
            item {
                AiRecommendPanel(
                    state = recommendState,
                    onGenerate = {
                        scope.launch {
                            recommendState = AiCallState.Loading
                            recommendState = try {
                                AiCallState.Success(
                                    resolvedRepository.loadAiHomeRecommend(
                                        size = 5,
                                        dramaId = dramaId,
                                    )
                                )
                            } catch (throwable: Throwable) {
                                AiCallState.Error(throwable.message ?: "生成推荐理由失败")
                            }
                        }
                    }
                )
            }
            item {
                AiQualityEvaluationPanel(
                    state = qualityEvaluationState,
                    onRefresh = {
                        qualityEvaluationRefreshTick += 1
                    }
                )
            }
            item {
                AiOperationsDashboardPanel(
                    state = operationsDashboardState,
                    episodeId = episodeId,
                    onRefresh = {
                        operationsDashboardRefreshTick += 1
                    }
                )
            }
        }
    }
}

@Composable
private fun AiEpisodePanel(
    episodeId: String,
    dramaId: String,
    onEpisodeIdChange: (String) -> Unit,
    onDramaIdChange: (String) -> Unit,
    onRefresh: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "体验入口",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            OutlinedTextField(
                value = dramaId,
                onValueChange = onDramaIdChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text(text = "剧集 ID") },
                singleLine = true,
            )
            OutlinedTextField(
                value = episodeId,
                onValueChange = onEpisodeIdChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text(text = "集数 ID") },
                singleLine = true,
            )
            Text(
                text = "默认可直接体验第 1 集。你也可以改成别的 episodeId 再点下面的按钮。",
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onRefresh) {
                Text(text = "刷新互动配置")
            }
        }
    }
}

@Composable
private fun AiInteractionPanel(
    state: AiCallState<InteractionConfig>,
    selectedNodeId: String,
    selectedOptionId: String,
    onSelectNode: (InteractionNode) -> Unit,
    onSelectOption: (InteractionOption) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "互动节点",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            when (state) {
                AiCallState.Idle, AiCallState.Loading -> {
                    CircularProgressIndicator()
                    Text(text = "正在加载互动配置")
                }
                is AiCallState.Error -> {
                    Text(
                        text = state.message,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                is AiCallState.Success -> {
                    Text(
                        text = "已加载 ${state.data.nodes.size} 个节点、${state.data.timelineItems.size} 条 timeline_items、${state.data.timedEvents.size} 条标准 timed events，点击节点和选项后可生成真实 AI 反馈。",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    state.data.generationPipeline?.let { pipeline ->
                        Text(
                            text = "生成链路：ASR/OCR/关键帧/弹幕热区 -> 候选节点 -> 人工确认 -> timeline_items",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = "证据来源：${pipeline.evidenceSources.ifEmpty { listOf("人工种子兜底") }.joinToString(" / ")}；候选 ${pipeline.candidateNodeCount} 个，确认 ${pipeline.confirmedNodeCount} 个，发布 ${pipeline.timelineItemCount} 条",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    HorizontalDivider()
                    state.data.timedEvents.takeIf { it.isNotEmpty() }?.let { events ->
                        Text(
                            text = "标准事件示例：${events.first().eventId} / ${events.first().componentType} / hash ${events.first().payloadHash}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                    state.data.nodes.forEach { node ->
                        val selected = node.id == selectedNodeId
                        val profile = node.componentProfile()
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            TextButton(onClick = { onSelectNode(node) }) {
                                Text(
                                    text = if (selected) "已选：${node.title}" else node.title
                                )
                            }
                            Text(
                                text = node.subtitle,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = "组件：${profile.displayName}（${node.componentType}）; 位置：${node.placement}; 来源：${node.generationSource}; 置信度：${node.confidence}; 复核：${node.reviewStatus.ifBlank { "unknown" }}",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = "语义：${profile.summary}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = "安全区：${profile.safeAreaHint}；默认位点：${profile.defaultPlacement}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            node.evidenceRefs.takeIf { it.isNotEmpty() }?.let { refs ->
                                Text(
                                    text = "可追溯证据：${refs.joinToString(" / ")}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            if (selected) {
                                node.options.forEach { option ->
                                    Button(
                                        onClick = { onSelectOption(option) },
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Text(
                                            text = if (option.id == selectedOptionId) {
                                                "已选：${option.text}"
                                            } else {
                                                option.text
                                            }
                                        )
                                    }
                                }
                            }
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun AiInteractionComponentPreviewPanel(
    state: AiCallState<InteractionConfig>,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "互动组件预览",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "把互动节点产品化为贴纸、选择卡、提示卡和剧情 X-Ray，便于答辩时直接展示组件形态。",
                style = MaterialTheme.typography.bodySmall
            )
            RenderAiState(state) { config ->
                val componentProfiles = config.nodes.map { it.componentProfile() }
                    .distinctBy { it.componentType }
                    .take(4)
                    .ifEmpty { listOf(InteractionComponentRegistry.resolve("CHOICE_CARD")) }
                componentProfiles.forEachIndexed { index, profile ->
                    val node = config.nodes.firstOrNull {
                        it.componentProfile().componentType == profile.componentType
                    } ?: config.nodes.firstOrNull()
                    ComponentPreviewCard(
                        title = profile.displayName,
                        subtitle = node?.title.orEmpty(),
                        description = profile.summary,
                        accent = componentAccent(profile.componentType, index),
                        trailing = buildList {
                            add("默认位点 ${profile.defaultPlacement}")
                            add("安全区 ${profile.safeAreaHint}")
                            node?.let { add("样例 ${it.placement} / 复核 ${it.reviewStatus.ifBlank { "unknown" }}") }
                        }.joinToString(" · "),
                    )
                }
                config.timedEvents.takeIf { it.isNotEmpty() }?.firstOrNull()?.let { event ->
                    val profile = event.componentProfile()
                    ComponentPreviewCard(
                        title = "${profile.displayName} 时间标签",
                        subtitle = "${formatMs(event.startMs)} - ${formatMs(event.endMs)}",
                        description = "标准 timed event 把组件、证据和时间窗口绑在一起，答辩时可以直接跳到对应镜头。",
                        accent = MaterialTheme.colorScheme.error,
                        trailing = "证据 ${event.evidenceRefs.takeIf { it.isNotEmpty() }?.joinToString(" / ") ?: "无"} · 复核 ${event.reviewStatus.ifBlank { "unknown" }} · hash ${event.payloadHash.take(8)}",
                    )
                }
                if (config.nodes.isNotEmpty()) {
                    val selected = config.nodes.first()
                    ComponentPreviewCard(
                        title = "剧情 X-Ray 信息层",
                        subtitle = selected.title,
                        description = "点击暂停或点击节点时展示当前人物、关系、证据来源、可跳转时间和安全区。",
                        accent = MaterialTheme.colorScheme.error,
                        trailing = "safeArea=${selected.safeArea.topDp}/${selected.safeArea.bottomDp}/${selected.safeArea.startDp}/${selected.safeArea.endDp}",
                    )
                }
            }
        }
    }
}

@Composable
private fun ComponentPreviewCard(
    title: String,
    subtitle: String,
    description: String,
    accent: Color,
    trailing: String,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(accent.copy(alpha = 0.08f), RoundedCornerShape(16.dp))
            .border(1.dp, accent.copy(alpha = 0.35f), RoundedCornerShape(16.dp))
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(text = title, fontWeight = FontWeight.SemiBold)
            if (subtitle.isNotBlank()) {
                Text(text = subtitle, style = MaterialTheme.typography.bodySmall)
            }
            Text(text = description, style = MaterialTheme.typography.bodySmall)
            if (trailing.isNotBlank()) {
                Text(
                    text = trailing,
                    style = MaterialTheme.typography.labelSmall,
                    color = accent
                )
            }
        }
    }
}

@Composable
private fun componentAccent(componentType: String, index: Int): Color {
    return when (componentType) {
        "REACTION_STICKER" -> MaterialTheme.colorScheme.primary
        "DANMAKU_STICKER" -> MaterialTheme.colorScheme.tertiary
        "AIGC_CARD" -> MaterialTheme.colorScheme.secondary
        "EVIDENCE_CARD" -> MaterialTheme.colorScheme.error
        "CHOICE_CARD" -> MaterialTheme.colorScheme.primaryContainer
        else -> when (index % 3) {
            0 -> MaterialTheme.colorScheme.primary
            1 -> MaterialTheme.colorScheme.tertiary
            else -> MaterialTheme.colorScheme.secondary
        }
    }
}

@Composable
private fun AiCandidateReviewPanel(
    state: AiCallState<List<InteractionCandidateNode>>,
    reviewState: AiCallState<InteractionCandidateReviewResult>,
    onReview: (InteractionCandidateNode, String) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "AI 编排候选审核",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "候选节点来自 ASR/OCR/关键帧/弹幕热区证据；只有 accepted 或 edited 会进入正式 timed events。",
                style = MaterialTheme.typography.bodySmall
            )
            when (reviewState) {
                AiCallState.Idle -> Unit
                AiCallState.Loading -> Text(text = "正在提交审核结果", style = MaterialTheme.typography.bodySmall)
                is AiCallState.Error -> Text(text = reviewState.message, color = MaterialTheme.colorScheme.error)
                is AiCallState.Success -> Text(
                    text = "最近审核：${reviewState.data.candidateId} -> ${reviewState.data.reviewStatus}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            when (state) {
                AiCallState.Idle, AiCallState.Loading -> {
                    CircularProgressIndicator()
                    Text(text = "正在加载候选节点")
                }
                is AiCallState.Error -> {
                    Text(text = state.message, color = MaterialTheme.colorScheme.error)
                }
                is AiCallState.Success -> {
                    if (state.data.isEmpty()) {
                        Text(text = "当前分集没有可审核候选")
                    }
                    state.data.forEach { candidate ->
                        val advice = candidate.orchestrationAdvice
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                text = "${formatMs(candidate.timeMs)} ${candidate.question.ifBlank { candidate.type }}",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "状态：${candidate.reviewStatus.ifBlank { "pending" }}；来源：${candidate.source}；置信度：${candidate.confidence}",
                                style = MaterialTheme.typography.bodySmall
                            )
                            candidate.reason.takeIf { it.isNotBlank() }?.let {
                                Text(text = it, style = MaterialTheme.typography.bodySmall)
                            }
                            if (advice.recommendedComponentType.isNotBlank()) {
                                Text(
                                    text = "编排建议：${advice.recommendedComponentType} / ${advice.visualStyle.ifBlank { "默认样式" }} / ${advice.placement.ifBlank { "默认位置" }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Text(
                                    text = "发布资格：${if (advice.publishEligible) "可发布" else "待审核"}；最大行数：${advice.maxLines}；${advice.evidenceSummary.ifBlank { "证据待补充" }}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Text(
                                    text = "安全区：顶部 ${advice.safeArea.topDp}dp / 右侧栏 ${advice.safeArea.avoidRightRail} / 底部进度 ${advice.safeArea.avoidProgressBar} / 弹幕 ${advice.safeArea.avoidDanmaku}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            candidate.options.takeIf { it.isNotEmpty() }?.let {
                                Text(
                                    text = "选项：${it.joinToString(" / ")}",
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                            candidate.evidenceRefs.takeIf { it.isNotEmpty() }?.let {
                                Text(
                                    text = "证据：${it.joinToString(" / ")}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                            Button(
                                onClick = { onReview(candidate, "accepted") },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(text = "接受")
                            }
                            Button(
                                onClick = { onReview(candidate, "edited") },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(text = "轻量编辑并接受")
                            }
                            TextButton(
                                onClick = { onReview(candidate, "rejected") },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(text = "拒绝")
                            }
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun AiDanmakuEmotionPanel(
    state: AiCallState<DanmakuEmotionReport>,
    onOpenPoint: (DanmakuEmotionPoint) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "观众共鸣点",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "基于聚合弹幕热区生成，不读取原始弹幕明细，可用于设计互动选择和特效。",
                style = MaterialTheme.typography.bodySmall
            )
            when (state) {
                AiCallState.Idle, AiCallState.Loading -> {
                    CircularProgressIndicator()
                    Text(text = "正在加载弹幕情绪报告")
                }
                is AiCallState.Error -> {
                    Text(text = state.message, color = MaterialTheme.colorScheme.error)
                }
                is AiCallState.Success -> {
                    Text(text = state.data.summary, style = MaterialTheme.typography.bodyMedium)
                    state.data.items.takeIf { it.isNotEmpty() }?.forEach { point ->
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                text = "${formatMs(point.timeMs)} ${point.emotion} / 热度 ${point.heatScore}",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = point.sceneSummary,
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = "关键词：${point.keywords.joinToString(" / ")}；弹幕强度：${point.commentIntensity}；点赞强度：${point.likeIntensity}",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = "建议互动：${point.suggestedInteraction}（${point.suggestedComponentType}）",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary,
                            )
                            point.evidenceRefs.takeIf { it.isNotEmpty() }?.let {
                                Text(
                                    text = "证据：${it.joinToString(" / ")}",
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                            TextButton(
                                onClick = { onOpenPoint(point) },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(text = "跳到该时间点播放")
                            }
                        }
                        HorizontalDivider()
                    } ?: Text(text = "当前分集暂无可用热区")
                }
            }
        }
    }
}

@Composable
private fun AiStorySummaryCachePanel(
    state: AiCallState<StorySummaryCacheStatus>,
    onRefresh: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "剧情简介缓存", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = "短剧总简介和每集简介预生成后直接加载，远端失败时不会覆盖最近一次成功产物。",
                style = MaterialTheme.typography.bodySmall
            )
            TextButton(onClick = onRefresh) {
                Text(text = "刷新缓存")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  来源：${result.source}")
                Text(text = "模型：${result.modelName.ifBlank { "未知" }}  耗时：${result.latencyMs} ms")
                Text(text = "Prompt：${result.promptVersion}", style = MaterialTheme.typography.bodySmall)
                if (result.degradeReason.isNotBlank()) {
                    Text(text = "降级原因：${result.degradeReason}", color = MaterialTheme.colorScheme.error)
                }
                if (result.latestAttempt.status != "missing") {
                    Text(
                        text = "最近尝试：${result.latestAttempt.status} / ${result.latestAttempt.source} / ${result.latestAttempt.latencyMs} ms",
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (result.latestAttempt.degradeReason.isNotBlank()) {
                        Text(
                            text = "尝试降级：${result.latestAttempt.degradeReason}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
                Text(text = "整剧简介：${result.dramaDescription}")
                result.episodes.takeIf { it.isNotEmpty() }?.let { episodes ->
                    Text(text = "分集简介：", fontWeight = FontWeight.SemiBold)
                    episodes.forEach { episode ->
                        Text(
                            text = "第${episode.episodeNo}集：${episode.summary}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AiRecapPanel(
    state: AiCallState<AiContentRecapResult>,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "剧情摘要", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            TextButton(onClick = onGenerate) {
                Text(text = "生成摘要")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                Text(text = "耗时：${result.latencyMs} ms  缓存：${result.cached}")
                ArtifactStatusLine(result.artifact)
                Text(text = "摘要：${result.summary}")
                result.highlights.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "看点：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                result.characterFocus.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "角色焦点：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                result.discussionSeeds.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "讨论种子：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                Text(text = "继续观看理由：${result.continueReason}")
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiVideoUnderstandingPanel(
    state: AiCallState<AiVideoUnderstandingResult>,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "视频理解", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            TextButton(onClick = onGenerate) {
                Text(text = "分析视频")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                Text(text = "耗时：${result.latencyMs} ms  缓存：${result.cached}")
                ArtifactStatusLine(result.artifact)
                Text(text = "摘要：${result.summary}")
                result.segments.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "剧情片段：")
                    it.take(4).forEach { item ->
                        Text(text = "• ${formatMs(item.startMs)}-${formatMs(item.endMs)} ${item.scene}")
                        item.visualEvents.takeIf { events -> events.isNotEmpty() }?.let { events ->
                            Text(text = events.joinToString(separator = "；"), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                result.interactionCandidates.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "互动候选：")
                    it.forEach { item ->
                        Text(text = "• ${formatMs(item.timeMs)} ${item.question}")
                        Text(text = item.reason, style = MaterialTheme.typography.bodySmall)
                        if (item.options.isNotEmpty()) {
                            Text(
                                text = "选项：${item.options.joinToString(separator = " / ")}",
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
                result.screenTextCues.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "屏幕文字识别：")
                    it.forEach { item ->
                        Text(text = "• ${formatMs(item.timeMs)} ${item.text}")
                        Text(text = item.reason, style = MaterialTheme.typography.bodySmall)
                    }
                }
                Text(
                    text = "音频文本：${result.audioText.status}${if (result.audioText.transcript.isNotBlank()) " / ${result.audioText.transcript}" else ""}",
                    style = MaterialTheme.typography.bodySmall
                )
                result.frameSampling.selectedFrames.takeIf { it.isNotEmpty() }?.let { frames ->
                    Text(text = "关键帧策略：互动触发点 + ASR 高能语句 + 基线锚点")
                    frames.forEach { frame ->
                        Text(
                            text = "• ${formatMs(frame.timeMs)} ${frame.source} / ${frame.reason}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                result.evidence.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "证据：${it.joinToString(separator = "；")}")
                }
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiAgnesGenerationPanel(
    statusState: AiCallState<AgnesStatusResult>,
    storyState: AiCallState<AiStoryContinuationResult>,
    checkinState: AiCallState<AiCheckinCardResult>,
    taskState: AiCallState<GenerationTaskResult>,
    generatedAssetState: AiCallState<GeneratedAssetManagementResult>,
    cleanupState: AiCallState<GeneratedAssetCleanupResult>,
    selectedCheckinStyle: String,
    onCheckinStyleSelected: (String) -> Unit,
    onRefreshStatus: () -> Unit,
    onGenerateStory: () -> Unit,
    onGenerateCheckin: () -> Unit,
    onCreateStoryTask: () -> Unit,
    onCreateCheckinTask: () -> Unit,
    onRefreshAssets: () -> Unit,
    onCleanupFailedAssets: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "Agnes 生成能力", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            RenderAiState(statusState) { status ->
                Text(text = "密钥状态：${if (status.configured) "已配置" else "未配置"} · 来源：${status.source.ifBlank { "none" }}")
                Text(text = "图片模型：${status.imageModel} / 视频模型：${status.videoModel}")
                Text(text = "网关：${status.baseUrl}", style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onRefreshStatus) {
                    Text(text = "刷新状态")
                }
                TextButton(onClick = onGenerateStory) {
                    Text(text = "生成续写视频")
                }
                TextButton(onClick = onGenerateCheckin) {
                    Text(text = "生成打卡图")
                }
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = "打卡风格模板",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                CHECKIN_CARD_STYLE_OPTIONS.chunked(3).forEach { rowItems ->
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        rowItems.forEach { option ->
                            val selected = option.id == selectedCheckinStyle
                            TextButton(onClick = { onCheckinStyleSelected(option.id) }) {
                                Text(text = if (selected) "✓ ${option.label}" else option.label)
                            }
                        }
                    }
                }
            }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.42f))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(text = "生成任务中心", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                Text(
                    text = "统一查看 Agnes 视频、Agnes 图片和本地模板任务，失败不会覆盖最后一次成功产物。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = onCreateStoryTask) {
                        Text(text = "任务续写")
                    }
                    TextButton(onClick = onCreateCheckinTask) {
                        Text(text = "任务打卡")
                    }
                }
                RenderAiState(taskState) { task ->
                    val taskMediaUrl = task.mediaAsset.localUrl
                        .ifBlank { task.mediaAsset.mediaUrl }
                        .ifBlank { task.mediaUrl }
                    Text(text = "任务：${task.taskType} · ${task.status}")
                    Text(text = "Provider：${task.provider.ifBlank { "unknown" }} · 模型：${task.modelName.ifBlank { "-" }}")
                    Text(text = "耗时：${task.latencyMs} ms · 分集：${task.episodeId}", style = MaterialTheme.typography.bodySmall)
                    if (task.resultTitle.isNotBlank()) {
                        Text(text = "标题：${task.resultTitle}")
                    }
                    if (task.taskType == "checkin_card" && taskMediaUrl.isNotBlank()) {
                        GeneratedCheckinImagePreview(
                            imageUrl = taskMediaUrl,
                            title = task.resultTitle.ifBlank { "剧情打卡海报" },
                        )
                    }
                    if (taskMediaUrl.isNotBlank()) {
                        Text(text = "产物：$taskMediaUrl", style = MaterialTheme.typography.bodySmall)
                    }
                    if (task.mediaAsset.cacheStatus.isNotBlank()) {
                        Text(
                            text = "产物缓存：${task.mediaAsset.cacheStatus}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (task.degradeReason.isNotBlank()) {
                        Text(text = "降级原因：${task.degradeReason}", color = MaterialTheme.colorScheme.error)
                    }
                    if (task.lastSuccess.mediaUrl.isNotBlank()) {
                        Text(
                            text = "最后成功产物：${task.lastSuccess.mediaUrl}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
            GeneratedAssetManagementCard(
                state = generatedAssetState,
                cleanupState = cleanupState,
                onRefresh = onRefreshAssets,
                onCleanupFailed = onCleanupFailedAssets,
            )
            RenderAiState(storyState) { result ->
                Text(text = "续写视频：${result.status} · Provider：${result.providerName.ifBlank { "unknown" }}")
                Text(text = "耗时：${result.latencyMs} ms · 模型：${result.modelName}")
                val mediaUrl = result.mediaAsset.localUrl
                    .ifBlank { result.mediaAsset.mediaUrl }
                    .ifBlank { result.mediaUrl }
                if (mediaUrl.isNotBlank()) {
                    Text(text = "视频地址：$mediaUrl", style = MaterialTheme.typography.bodySmall)
                }
                if (result.mediaAsset.cacheStatus.isNotBlank()) {
                    Text(
                        text = "产物缓存：${result.mediaAsset.cacheStatus}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(text = "标题：${result.title}")
                Text(text = "钩子：${result.viewerHook}")
                ArtifactStatusLine(result.artifact)
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
            RenderAiState(checkinState) { result ->
                val imageUrl = result.mediaAsset.localUrl
                    .ifBlank { result.mediaAsset.mediaUrl }
                    .ifBlank { result.imageUrl }
                Text(text = "打卡图：${result.cardStatus.ifBlank { result.status }} · Provider：${result.provider}")
                Text(text = "风格：${result.styleLabel.ifBlank { result.style }} · 耗时：${result.cardLatencyMs} ms · 模型：${result.modelName}")
                if (imageUrl.isNotBlank()) {
                    GeneratedCheckinImagePreview(
                        imageUrl = imageUrl,
                        title = result.title.ifBlank { "剧情打卡海报" },
                    )
                    Text(text = "图片地址：$imageUrl", style = MaterialTheme.typography.bodySmall)
                }
                if (result.mediaAsset.cacheStatus.isNotBlank()) {
                    Text(
                        text = "产物缓存：${result.mediaAsset.cacheStatus}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(text = "标题：${result.title}")
                Text(text = "Prompt：${result.prompt.take(96)}${if (result.prompt.length > 96) "…" else ""}")
                ArtifactStatusLine(result.artifact)
                val reason = result.cardDegradeReason.ifBlank { result.degradeReason.orEmpty() }
                if (reason.isNotBlank()) {
                    Text(text = "降级原因：$reason", color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

@Composable
private fun GeneratedAssetManagementCard(
    state: AiCallState<GeneratedAssetManagementResult>,
    cleanupState: AiCallState<GeneratedAssetCleanupResult>,
    onRefresh: () -> Unit,
    onCleanupFailed: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.42f))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = "生成产物管理", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TextButton(onClick = onRefresh) {
                    Text(text = "刷新")
                }
                TextButton(onClick = onCleanupFailed) {
                    Text(text = "清理失败")
                }
            }
        }
        RenderAiState(state) { result ->
            Text(
                text = "成功 ${result.summary.successCount} · 失败/降级 ${result.summary.failedCount} · 缓存 ${formatBytes(result.summary.cachedByteSize)} · 来源 ${result.summary.source}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            result.recentSuccesses.take(3).forEach { item ->
                GeneratedAssetLine(item = item, success = true)
            }
            if (result.failedAttempts.isNotEmpty()) {
                Text(
                    text = "失败尝试",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                )
                result.failedAttempts.take(2).forEach { item ->
                    GeneratedAssetLine(item = item, success = false)
                }
            }
        }
        RenderAiState(cleanupState) { result ->
            Text(
                text = "已清理 ${result.deletedCount} 条失败/降级记录",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun GeneratedAssetLine(
    item: GeneratedAssetManagementItem,
    success: Boolean,
) {
    val localUrl = item.mediaAsset.localUrl.ifBlank { item.mediaAsset.mediaUrl }.ifBlank { item.mediaUrl }
    Text(
        text = "${if (success) "✓" else "!"} ${item.title.ifBlank { item.taskType }} · ${item.status} · ${item.provider.ifBlank { "unknown" }} · ${formatBytes(item.mediaAsset.byteSize)}",
        style = MaterialTheme.typography.bodySmall,
        color = if (success) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error,
    )
    if (localUrl.isNotBlank()) {
        Text(
            text = "本地：$localUrl",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    if (item.mediaAsset.remoteUrl.isNotBlank()) {
        Text(
            text = "远端：${item.mediaAsset.remoteUrl}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    if (item.degradeReason.isNotBlank()) {
        Text(
            text = "原因：${item.degradeReason}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.error,
        )
    }
}

private fun formatBytes(value: Long): String {
    return when {
        value >= 1024L * 1024L -> "${value / (1024L * 1024L)} MB"
        value >= 1024L -> "${value / 1024L} KB"
        else -> "$value B"
    }
}

@Composable
private fun AiFeedbackPanel(
    state: AiCallState<AiInteractionFeedbackResult>,
    selectedNode: InteractionNode?,
    selectedOption: InteractionOption?,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "互动反馈", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = buildString {
                    append("当前节点：")
                    append(selectedNode?.title ?: "未选择")
                    append("；当前选项：")
                    append(selectedOption?.text ?: "未选择")
                },
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onGenerate) {
                Text(text = "生成反馈")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                ArtifactStatusLine(result.artifact)
                Text(text = "反馈：${result.feedbackText}")
                Text(text = "解释：${result.selectionExplanation}")
                Text(text = "追问：${result.followupQuestion}")
                result.derivedTags.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "衍生标签：")
                    it.forEach { item -> Text(text = "• ${item.tagId} / ${item.score}") }
                }
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

private fun formatMs(value: Long): String {
    val totalSeconds = value / 1000L
    val minutes = totalSeconds / 60L
    val seconds = totalSeconds % 60L
    return "%02d:%02d".format(minutes, seconds)
}

private fun formatRate(value: Double): String {
    return String.format(java.util.Locale.US, "%.1f%%", value * 100)
}

private fun formatDecimal(value: Double): String {
    return String.format(java.util.Locale.US, "%.2f", value)
}

@Composable
private fun AiTagPanel(
    state: AiCallState<AiTagExtractResult>,
    selectedNode: InteractionNode?,
    selectedOption: InteractionOption?,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "标签抽取", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = "当前节点：${selectedNode?.title ?: "未选择"}；当前选项：${selectedOption?.text ?: "未选择"}",
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onGenerate) {
                Text(text = "抽取标签")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                ArtifactStatusLine(result.artifact)
                Text(text = "内容标签：")
                result.contentTags.forEach { item -> Text(text = "• ${item.tagId} / ${item.score}") }
                Text(text = "互动标签：")
                result.interactionTags.forEach { item -> Text(text = "• ${item.tagId} / ${item.score}") }
                Text(text = "用户画像更新：")
                result.userProfileTagUpdates.forEach { item ->
                    Text(text = "• ${item.tagId} / ${item.delta}")
                }
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiModerationPanel(
    text: String,
    state: AiCallState<AiModerationResult>,
    onTextChange: (String) -> Unit,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "内容审核", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            OutlinedTextField(
                value = text,
                onValueChange = onTextChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text(text = "待审核文本") },
                minLines = 3,
            )
            TextButton(onClick = onGenerate) {
                Text(text = "开始审核")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  结论：${result.decision}")
                Text(text = "风险词：${result.matchedKeywords.joinToString(separator = "、")}")
                Text(text = "风险标记：${result.riskFlags.joinToString(separator = "、")}")
                Text(text = "审核内容：${result.reviewText}")
                result.blockReason?.let { Text(text = "拦截原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiDiscussionPanel(
    state: AiCallState<AiDiscussionSeedResult>,
    selectedNode: InteractionNode?,
    selectedOption: InteractionOption?,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "讨论延展", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = "基于节点「${selectedNode?.title ?: "未选择"}」和选项「${selectedOption?.text ?: "未选择"}」生成讨论问题、角色视角和预测话题。",
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onGenerate) {
                Text(text = "生成讨论")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                ArtifactStatusLine(result.artifact)
                Text(text = "讨论问题：")
                result.discussionQuestions.forEach { item -> Text(text = "• $item") }
                result.characterPerspectives.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "角色视角：")
                    it.forEach { item -> Text(text = "• ${item.name}：${item.question}") }
                }
                result.nextEpisodePredictions.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "后续预测：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                result.alternateChoiceTopics.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "换选项话题：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                Text(text = "分享文案：${result.shareText}")
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiHistoryRecapPanel(
    state: AiCallState<AiHistoryRecapResult>,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "历史续播", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            TextButton(onClick = onGenerate) {
                Text(text = "生成续播总结")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                ArtifactStatusLine(result.artifact)
                Text(text = "总结：${result.summary}")
                Text(text = "建议续播：${result.nextEpisodeId}")
                Text(text = "理由：${result.continueReason}")
                result.items.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "历史条目：")
                    it.forEach { item ->
                        Text(text = "• ${item.episodeTitle} / ${item.progressText}")
                        Text(text = item.recap, style = MaterialTheme.typography.bodySmall)
                    }
                }
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiRecommendPanel(
    state: AiCallState<AiHomeRecommendResult>,
    onGenerate: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "推荐理由", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            TextButton(onClick = onGenerate) {
                Text(text = "生成推荐")
            }
            RenderAiState(state) { result ->
                Text(text = "状态：${result.status}  模型：${result.modelName}")
                ArtifactStatusLine(result.artifact)
                Text(text = "策略：${result.strategy}")
                result.personalizationSignals.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "个性化信号：")
                    it.forEach { item -> Text(text = "• $item") }
                }
                result.items.takeIf { it.isNotEmpty() }?.let {
                    Text(text = "推荐内容：")
                    it.forEach { item ->
                        Text(text = "• TOP${item.rank} ${item.title} / ${item.score}")
                        Text(text = item.reason, style = MaterialTheme.typography.bodySmall)
                    }
                }
                result.degradeReason?.let { Text(text = "降级原因：$it", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun AiQualityEvaluationPanel(
    state: AiCallState<QualityEvaluationResult>,
    onRefresh: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "质量评测集", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = "把剧情简介和互动产物纳入固定回归检查，保证无技术痕迹、非分集拼接、时间线字段稳定。",
                style = MaterialTheme.typography.bodySmall
            )
            TextButton(onClick = onRefresh) {
                Text(text = "刷新评测")
            }
            RenderAiState(state) { result ->
                Text(
                    text = "套件：${result.suiteVersion}；来源：${result.source}",
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    text = "通过 ${result.summary.passed}/${result.summary.total}；失败 ${result.summary.failed}；通过率 ${formatRate(result.summary.passRate)}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (result.summary.failed == 0) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.error
                    }
                )
                result.checks.forEach { check ->
                    Text(
                        text = "${if (check.passed) "通过" else "失败"} · ${check.name}",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = if (check.passed) FontWeight.Normal else FontWeight.SemiBold,
                        color = if (check.passed) {
                            MaterialTheme.colorScheme.onSecondaryContainer
                        } else {
                            MaterialTheme.colorScheme.error
                        }
                    )
                    Text(
                        text = "  ${check.checkId} / ${check.severity} / ${check.detail}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (!check.passed && check.targets.isNotEmpty()) {
                        Text(
                            text = "  失败对象：${check.targets.take(3).joinToString()}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AiOperationsDashboardPanel(
    state: AiCallState<OperationsDashboardResult>,
    episodeId: String,
    onRefresh: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(text = "运营看板", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                text = "数据范围：${episodeId.ifBlank { "全局" }}；数据源：SQLite 持久化",
                style = MaterialTheme.typography.bodySmall
            )
            TextButton(onClick = onRefresh) {
                Text(text = "刷新看板")
            }
            RenderAiState(state) { result ->
                AiOperationsOverviewBlock(result)
                AiOperationsTrendSummaryBlock(result.trendSummary)
                AiOperationsTrendBlock(result.trend)
                AiOperationsHotNodesBlock(result.hotNodes)
                AiOperationsAiQualityBlock(result.ai.capabilities)
                AiOperationsAgnesBlock(result.agnesGeneration)
                AiHighlightStrategyBlock(result.highlightStrategies)
                AiOperationsProfileBlock(result.profile)
            }
        }
    }
}

@Composable
private fun AiOperationsOverviewBlock(result: OperationsDashboardResult) {
    Text(
        text = "存储：${result.storage.engine}${if (result.storage.persistent) " / 持久化" else ""}",
        style = MaterialTheme.typography.bodyMedium
    )
    Text(text = "互动 CTR：${formatRate(result.overview.interactionCtr)}")
    DashboardLine("曝光 ${result.overview.interactionImpressions} / 点击 ${result.overview.interactionSubmits}")
    Text(text = "插片完成率：${formatRate(result.overview.insertPlaybackCompletionRate)}")
    DashboardLine("AI 成功率：${formatRate(result.overview.aiSuccessRate)} / 降级率：${formatRate(result.overview.aiDegradedRate)}")
    Text(text = "AI p95 延迟：${result.overview.aiP95LatencyMs} ms")
    DashboardLine("观看 ${result.overview.watchEpisodeCount} 集 / 完成 ${result.overview.watchCompletedCount} 集；收藏 ${result.overview.savedMomentCount} 个；事件 ${result.overview.eventCount} 条")
    DashboardSectionTitle("播放 QoE")
    DashboardLine("起播 ${result.overview.firstFrameRendered}/${result.overview.videoStartAttempts} / 成功率 ${formatRate(result.overview.startupSuccessRate)} / 失败率 ${formatRate(result.overview.startupFailureRate)}")
    DashboardLine("首帧 p50 ${result.overview.startupP50Ms} ms / p95 ${result.overview.startupP95Ms} ms；重缓冲 ${result.overview.rebufferCount} 次 / p95 ${result.overview.rebufferP95Ms} ms / 总 ${result.overview.rebufferTotalMs} ms；起播前退出 ${result.overview.exitBeforeStartCount}")
}

@Composable
private fun AiOperationsTrendSummaryBlock(summary: OperationsDashboardTrendSummary) {
    DashboardSectionTitle("趋势诊断")
    DashboardLine("活跃 ${summary.activeDayCount} 天；最佳 CTR 日 ${summary.bestCtrDay.ifBlank { "暂无" }} ${formatRate(summary.bestCtr)}；最佳策略 ${summary.bestStrategyLabel.ifBlank { summary.bestStrategy.ifBlank { "暂无" } }} ${formatRate(summary.bestStrategyCtr)}")
    Text(
        text = "状态：${if (summary.qualityStatus == "healthy") "健康" else "需关注"}",
        style = MaterialTheme.typography.bodySmall,
        color = if (summary.qualityStatus == "healthy") {
            MaterialTheme.colorScheme.primary
        } else {
            MaterialTheme.colorScheme.error
        }
    )
    summary.riskNotes.forEach { note ->
        DashboardLine("• $note", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun AiOperationsTrendBlock(trend: List<OperationsDashboardTrendPoint>) {
    if (trend.isEmpty()) return
    DashboardSectionTitle("趋势视图")
    trend.takeLast(7).forEach { point ->
        DashboardLine("• ${point.label} / CTR ${formatRate(point.interactionCtr)} / 完播 ${formatRate(point.watchCompletionRate)} / AI ${formatRate(point.aiSuccessRate)} / p95 ${point.aiP95LatencyMs} ms")
        DashboardLine("  曝光 ${point.interactionImpressions} / 点击 ${point.interactionSubmits} / 播放 ${point.insertPlaybackCompleted}/${point.insertPlaybackStarts} / 错误 ${point.playbackErrorCount}")
        DashboardLine("  起播 ${point.firstFrameRendered}/${point.videoStartAttempts} / 成功 ${formatRate(point.startupSuccessRate)} / 失败 ${formatRate(point.startupFailureRate)} / 首帧p95 ${point.startupP95Ms} ms / 重缓冲 ${point.rebufferCount} 次 ${point.rebufferTotalMs} ms")
    }
}

@Composable
private fun AiOperationsHotNodesBlock(nodes: List<OperationsDashboardHotNode>) {
    if (nodes.isEmpty()) return
    DashboardSectionTitle("热节点：")
    nodes.take(3).forEach { node ->
        DashboardLine("• ${node.nodeTitle.ifBlank { node.nodeId }} / 曝光 ${node.impressions} / 点击 ${node.submits} / ${formatRate(node.ctr)}")
        if (node.choices.isNotEmpty()) {
            DashboardLine("  选项：${node.choices.joinToString(separator = " / ") { "${it.optionText}(${it.selects})" }}")
        }
    }
}

@Composable
private fun AiOperationsAiQualityBlock(capabilities: List<OperationsDashboardAiCapability>) {
    if (capabilities.isEmpty()) return
    DashboardSectionTitle("AI 质量：")
    capabilities.take(3).forEach { capability ->
        DashboardLine("• ${capability.capability} / 成功 ${capability.successCount} / 降级 ${capability.degradedCount} / ${formatRate(capability.successRate)} / ${capability.p95LatencyMs} ms")
    }
}

@Composable
private fun AiOperationsAgnesBlock(report: OperationsDashboardAgnesGeneration) {
    if (report.totalStarts == 0 && report.totalSuccess == 0 && report.totalDegraded == 0) return
    DashboardSectionTitle("Agnes 生成质量：")
    DashboardLine(
        "• 总触发 ${report.totalStarts} / 成功 ${report.totalSuccess} / 降级 ${report.totalDegraded} / 成功率 ${formatRate(report.successRate)} / p95 ${report.p95LatencyMs} ms"
    )
    DashboardLine(
        "  图片 ${report.image.success}/${report.image.starts} 成功 ${formatRate(report.image.successRate)}；视频 ${report.video.success}/${report.video.starts} 成功 ${formatRate(report.video.successRate)}"
    )
    DashboardLine(
        "  本地模板兜底 ${report.localTemplateFallbackCount} 次；图片降级 ${formatRate(report.image.degradedRate)} / 视频降级 ${formatRate(report.video.degradedRate)}"
    )
}

@Composable
private fun AiHighlightStrategyBlock(strategies: List<OperationsDashboardHighlightStrategy>) {
    if (strategies.isEmpty()) return
    DashboardSectionTitle("高能策略对照：")
    strategies.take(3).forEach { strategy ->
        DashboardLine("• ${strategy.label.ifBlank { strategy.selectionStrategy }} / 曝光 ${strategy.impressions} / 点击 ${strategy.clicks} / 跳转 ${strategy.jumps}(${formatRate(strategy.jumpRate)}) / CTR ${formatRate(strategy.ctr)}")
        DashboardLine("  平均排名 ${formatDecimal(strategy.averageRank)} / 去重片段 ${strategy.uniqueMomentCount} / 完播 ${strategy.playCompleted}(${formatRate(strategy.completionRate)}) / 收藏 ${strategy.saved}(${formatRate(strategy.saveRate)})")
    }
}

@Composable
private fun AiOperationsProfileBlock(profile: OperationsDashboardProfileSummary) {
    profile.interestTags.takeIf { it.isNotEmpty() }?.let { tags ->
        Text(text = "画像标签：${tags.joinToString(separator = " / ")}")
    }
    profile.interestTagDistribution.takeIf { it.isNotEmpty() }?.let { distribution ->
        DashboardSectionTitle("画像分布：")
        distribution.take(5).forEach { item ->
            DashboardLine("• ${item.tag} x${item.count}")
        }
    }
    profile.recommendReason.takeIf { it.isNotBlank() }?.let {
        DashboardLine("推荐理由：$it")
    }
    profile.topNodes.takeIf { it.isNotEmpty() }?.let { nodes ->
        DashboardSectionTitle("画像触发节点：")
        nodes.forEach { node ->
            DashboardLine("• ${node.nodeTitle.ifBlank { node.nodeId }} / 提交 ${node.submits}")
        }
    }
}

@Composable
private fun DashboardSectionTitle(text: String) {
    Text(text = text, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun DashboardLine(
    text: String,
    color: Color = MaterialTheme.colorScheme.onSurface,
) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodySmall,
        color = color,
    )
}

@Composable
private fun <T> RenderAiState(
    state: AiCallState<T>,
    content: @Composable (T) -> Unit,
) {
    when (state) {
        AiCallState.Idle -> Text(text = "尚未生成结果")
        AiCallState.Loading -> {
            CircularProgressIndicator()
            Text(text = "生成中，请稍等")
        }
        is AiCallState.Error -> Text(
            text = state.message,
            color = MaterialTheme.colorScheme.error
        )
        is AiCallState.Success -> content(state.data)
    }
}

@Composable
private fun ArtifactStatusLine(artifact: AiArtifactMeta) {
    if (artifact.source.isBlank()) {
        return
    }
    val sourceText = when (artifact.source) {
        "remote_model" -> "远端模型成功生成"
        "memory_cache" -> "运行时缓存"
        "persistent_json" -> "持久化结果"
        "last_success_artifact" -> "最近一次成功产物回放"
        "local_fallback" -> "本地降级生成"
        "local_rule" -> "本地规则"
        else -> artifact.source
    }
    val versionText = if (artifact.version > 0) " v${artifact.version}" else ""
    Text(text = "产物来源：$sourceText$versionText", style = MaterialTheme.typography.bodySmall)
    if (artifact.restoredFromLastSuccess) {
        Text(
            text = "本次调用已降级，界面继续展示最近成功版本 v${artifact.lastSuccessVersion}",
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodySmall
        )
    }
}
