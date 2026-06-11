@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.shortdrama.plotunderstanding.feature.home

import android.content.Context
import android.content.Intent
import android.view.TextureView
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items as gridItems
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Timeline
import com.shortdrama.plotunderstanding.core.ui.AigcModeToggle
import com.shortdrama.plotunderstanding.core.ui.AigcScreenScaffold
import com.shortdrama.plotunderstanding.core.ui.AigcThemeMode
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.database.StandaloneDatabaseProvider
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor
import androidx.media3.datasource.cache.SimpleCache
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import java.text.SimpleDateFormat
import java.io.File
import java.util.Date
import java.util.Locale
import java.util.UUID
import kotlin.math.abs
import kotlin.math.min
import kotlin.math.roundToInt

internal sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>

    data class Success<T>(val data: T) : LoadState<T>

    data class Error(val message: String) : LoadState<Nothing>
}

@Composable
fun rememberRepository(): ShortPlayRepository {
    return remember { BackendShortPlayRepository() }
}

private var homeDramaCardsMemoryCache: List<HomeDramaCard>? = null

@Composable
fun HomeRoute(
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenDrama: (String) -> Unit,
    onOpenEpisode: (String, Long) -> Unit = { _, _ -> },
    onOpenAi: () -> Unit = {},
    repository: ShortPlayRepository? = null,
) {
    val resolvedRepository = repository ?: rememberRepository()
    val context = LocalContext.current
    val telemetryDispatcher = remember(resolvedRepository) { BackendTelemetryDispatcher(resolvedRepository) }
    val coroutineScope = rememberCoroutineScope()
    var retryTick by remember { mutableStateOf(0) }
    var highlightStrategy by rememberSaveable { mutableStateOf("heat_score_desc_v1") }
    var defenseDemoModeEnabled by rememberSaveable { mutableStateOf(false) }
    var homeMenuExpanded by rememberSaveable { mutableStateOf(false) }
    val state by produceState<LoadState<List<HomeDramaCard>>>(
        initialValue = homeDramaCardsMemoryCache?.let { LoadState.Success(it) } ?: LoadState.Loading,
        retryTick,
        resolvedRepository
    ) {
        value = try {
            val items = resolvedRepository.loadHome()
            homeDramaCardsMemoryCache = items
            LoadState.Success(items)
        } catch (throwable: Throwable) {
            homeDramaCardsMemoryCache?.let { LoadState.Success(it) }
                ?: LoadState.Error(throwable.message ?: "首页加载失败")
        }
    }
    val highlightState by produceState<LoadState<List<ShareableMoment>>>(
        initialValue = LoadState.Loading,
        retryTick,
        highlightStrategy,
        resolvedRepository
    ) {
        value = try {
            LoadState.Success(resolvedRepository.loadHomeHighlightFeed(strategy = highlightStrategy))
        } catch (throwable: Throwable) {
            LoadState.Error(throwable.message ?: "高能切片流加载失败")
        }
    }
    val demoModeState by produceState<LoadState<DefenseDemoModeStatus>>(
        initialValue = LoadState.Loading,
        retryTick,
        resolvedRepository,
    ) {
        value = try {
            LoadState.Success(resolvedRepository.loadDemoMode())
        } catch (throwable: Throwable) {
            LoadState.Error(throwable.message ?: "演示模式加载失败")
        }
    }

    LaunchedEffect(resolvedRepository) {
        telemetryDispatcher.track(
            context = context,
            events = listOf(pageViewEvent("home"))
        )
    }

    LaunchedEffect(state) {
        val items = (state as? LoadState.Success<List<HomeDramaCard>>)?.data ?: return@LaunchedEffect
        telemetryDispatcher.track(
            context = context,
            events = items.map { drama ->
                homeContentSourceEvent(
                    dramaId = drama.dramaId,
                    contentSource = drama.contentSource,
                )
            }
        )
    }

    LaunchedEffect(highlightState) {
        val moments = (highlightState as? LoadState.Success<List<ShareableMoment>>)?.data.orEmpty()
        if (moments.isEmpty()) {
            return@LaunchedEffect
        }
        telemetryDispatcher.track(
            context = context,
            events = moments.take(3).mapIndexed { index, moment ->
                homeHighlightMomentEvent(
                    eventName = "home_highlight_impression",
                    moment = moment,
                    rank = index + 1,
                )
            }
        )
    }

    LaunchedEffect(defenseDemoModeEnabled, demoModeState) {
        val mode = (demoModeState as? LoadState.Success<DefenseDemoModeStatus>)?.data ?: return@LaunchedEffect
        if (defenseDemoModeEnabled && mode.fixedStrategy.isNotBlank()) {
            highlightStrategy = mode.fixedStrategy
        }
    }

    AigcScreenScaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    scrolledContainerColor = Color.Transparent,
                ),
                navigationIcon = {
                    Box {
                        IconButton(onClick = { homeMenuExpanded = true }) {
                            Icon(
                                imageVector = Icons.Default.Menu,
                                contentDescription = "首页功能菜单",
                            )
                        }
                        HomeOverflowMenu(
                            expanded = homeMenuExpanded,
                            defenseDemoModeEnabled = defenseDemoModeEnabled,
                            highlightState = highlightState,
                            onDismiss = { homeMenuExpanded = false },
                            onOpenAi = {
                                homeMenuExpanded = false
                                onOpenAi()
                            },
                            onOpenHistory = {
                                homeMenuExpanded = false
                                onOpenHistory()
                            },
                            onToggleDefenseDemo = {
                                homeMenuExpanded = false
                                defenseDemoModeEnabled = !defenseDemoModeEnabled
                            },
                            onOpenDemoRoute = {
                                val mode = (demoModeState as? LoadState.Success<DefenseDemoModeStatus>)?.data
                                homeMenuExpanded = false
                                if (mode != null) {
                                    onOpenEpisode(mode.entry.episodeId, mode.entry.startMs)
                                }
                            },
                            onOpenFirstHighlight = {
                                val moment = (highlightState as? LoadState.Success<List<ShareableMoment>>)
                                    ?.data
                                    ?.firstOrNull()
                                homeMenuExpanded = false
                                if (moment != null) {
                                    coroutineScope.launch {
                                        telemetryDispatcher.track(
                                            context = context,
                                            events = listOf(
                                                homeHighlightMomentEvent(
                                                    eventName = "home_highlight_menu_jump",
                                                    moment = moment,
                                                    rank = 1,
                                                )
                                            )
                                        )
                                    }
                                    onOpenEpisode(moment.episodeId, moment.startMs)
                                }
                            },
                        )
                    }
                },
                title = { Text(text = "短剧") },
                actions = {
                    AigcModeToggle(
                        themeMode = themeMode,
                        onToggle = onToggleTheme,
                        modifier = Modifier.padding(end = 10.dp),
                    )
                },
            )
        }
    ) { padding ->
        when (val current = state) {
            LoadState.Loading -> LoadingPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = "正在加载推荐内容"
            )

            is LoadState.Error -> ErrorPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = current.message,
                onRetry = { retryTick += 1 }
            )

            is LoadState.Success -> LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                gridItems(current.data, key = { it.dramaId }) { drama ->
                    DramaCard(
                        drama = drama,
                        onClick = { onOpenDrama(drama.dramaId) }
                    )
                }
            }

        }
    }
}

@Composable
private fun HomeOverflowMenu(
    expanded: Boolean,
    defenseDemoModeEnabled: Boolean,
    highlightState: LoadState<List<ShareableMoment>>,
    onDismiss: () -> Unit,
    onOpenAi: () -> Unit,
    onOpenHistory: () -> Unit,
    onToggleDefenseDemo: () -> Unit,
    onOpenDemoRoute: () -> Unit,
    onOpenFirstHighlight: () -> Unit,
) {
    val hasHighlight = (highlightState as? LoadState.Success<List<ShareableMoment>>)
        ?.data
        ?.isNotEmpty() == true
    DropdownMenu(
        expanded = expanded,
        onDismissRequest = onDismiss,
    ) {
        DropdownMenuItem(
            text = { Text("观看历史") },
            onClick = onOpenHistory,
        )
        DropdownMenuItem(
            text = { Text(if (defenseDemoModeEnabled) "答辩演示模式：开" else "答辩演示模式：关") },
            onClick = onToggleDefenseDemo,
        )
        if (defenseDemoModeEnabled) {
            DropdownMenuItem(
                text = { Text("AI 体验") },
                onClick = onOpenAi,
            )
            DropdownMenuItem(
                text = { Text("进入答辩演示路线") },
                onClick = onOpenDemoRoute,
            )
            DropdownMenuItem(
                text = { Text(if (hasHighlight) "播放首个高能切片" else "高能切片加载中") },
                enabled = hasHighlight,
                onClick = onOpenFirstHighlight,
            )
        }
    }
}

@Composable
fun DramaDetailRoute(
    dramaId: String,
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onPlayEpisode: (String, Long) -> Unit,
    onBack: () -> Unit,
    repository: ShortPlayRepository? = null,
) {
    val resolvedRepository = repository ?: rememberRepository()
    val context = LocalContext.current
    val telemetryDispatcher = remember(resolvedRepository) { BackendTelemetryDispatcher(resolvedRepository) }
    var retryTick by remember { mutableStateOf(0) }
    var summaryRefreshTick by remember { mutableStateOf(0) }
    val state by produceState<LoadState<DramaDetailScreenState>>(
        initialValue = LoadState.Loading,
        dramaId,
        retryTick,
        resolvedRepository
    ) {
        value = try {
            val detail = resolvedRepository.loadDrama(dramaId)
            val episodes = resolvedRepository.loadEpisodes(dramaId)
            val savedMoments = try {
                resolvedRepository.loadSavedMoments(dramaId)
            } catch (_: Throwable) {
                emptyList()
            }
            LoadState.Success(DramaDetailScreenState(detail, episodes, savedMoments))
        } catch (throwable: Throwable) {
            LoadState.Error(throwable.message ?: "详情加载失败")
        }
    }

    val storySummaryState by produceState<LoadState<StorySummaryCacheStatus>>(
        initialValue = LoadState.Loading,
        dramaId,
        retryTick,
        summaryRefreshTick,
        resolvedRepository
    ) {
        value = try {
            LoadState.Success(resolvedRepository.loadStorySummaryCacheStatus(dramaId))
        } catch (throwable: Throwable) {
            LoadState.Error(throwable.message ?: "剧情简介缓存状态加载失败")
        }
    }

    LaunchedEffect(dramaId, resolvedRepository) {
        telemetryDispatcher.track(
            context = context,
            events = listOf(
                pageViewEvent(
                    screenName = "detail",
                    dramaId = dramaId
                )
            )
        )
    }

    AigcScreenScaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    scrolledContainerColor = Color.Transparent,
                ),
                title = { Text(text = "剧集详情") },
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
        when (val current = state) {
            LoadState.Loading -> LoadingPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = "正在加载详情和集数"
            )

            is LoadState.Error -> ErrorPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = current.message,
                onRetry = { retryTick += 1 }
            )

            is LoadState.Success -> LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                item {
                    DetailHeader(
                        detail = current.data.detail,
                        episodes = current.data.episodes,
                        onEpisodeClick = { episode -> onPlayEpisode(episode.episodeId, 0L) },
                    )
                }
                item {
                    DetailMoreContentPanel(
                        storySummaryState = storySummaryState,
                        savedMoments = current.data.savedMoments,
                        onRefreshSummary = { summaryRefreshTick += 1 },
                        onOpenMoment = { moment -> onPlayEpisode(moment.episodeId, moment.startMs) },
                    )
                }
            }
        }
    }
}

@Composable
fun PlayerRoute(
    episodeId: String,
    initialPositionMs: Long = 0L,
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onPlayEpisode: (String, Long) -> Unit,
    onBack: () -> Unit,
    repository: ShortPlayRepository? = null,
) {
    val resolvedRepository = repository ?: rememberRepository()
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    val telemetryDispatcher = remember(resolvedRepository) { BackendTelemetryDispatcher(resolvedRepository) }
    var retryTick by remember { mutableStateOf(0) }
    val state by produceState<LoadState<PlayerScreenState>>(
        initialValue = LoadState.Loading,
        episodeId,
        retryTick,
        resolvedRepository
    ) {
        value = try {
            val playbackEpisode = resolvedRepository.loadPlayEpisode(episodeId)
            val interactionConfig = resolvedRepository.loadInteractionConfig(episodeId)
            val episodeSummary = runCatching {
                resolvedRepository.loadEpisodes(dramaIdFromEpisodeId(episodeId))
                    .firstOrNull { it.episodeId == episodeId }
                    ?.summary
                    .orEmpty()
            }.getOrDefault("")
            LoadState.Success(PlayerScreenState(playbackEpisode, interactionConfig, episodeSummary))
        } catch (throwable: Throwable) {
            LoadState.Error(throwable.message ?: "播放页加载失败")
        }
    }

    when (val current = state) {
        LoadState.Loading -> Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            IconButton(
                onClick = onBack,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(8.dp)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "返回",
                    tint = Color.White,
                )
            }
            CircularProgressIndicator(
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(28.dp),
                color = Color.White,
            )
        }

        is LoadState.Error -> AigcScreenScaffold(
            topBar = {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                        scrolledContainerColor = Color.Transparent,
                    ),
                    title = { Text(text = "播放器") },
                    navigationIcon = { TextButton(onClick = onBack) { Text(text = "返回") } },
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
            ErrorPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = current.message,
                onRetry = { retryTick += 1 }
            )
        }

        is LoadState.Success -> {
            val playbackEpisode = current.data.playbackEpisode
            val interactionConfig = current.data.interactionConfig
            val mainPlayUrl = playbackEpisode.preferredPlayUrl.ifBlank { playbackEpisode.playUrl }
            var currentPlayUrl by remember(playbackEpisode.episodeId) {
                mutableStateOf(mainPlayUrl)
            }
            val exoPlayer = remember(playbackEpisode.episodeId, initialPositionMs) {
                buildShortPlayPlayer(
                    context = context,
                    playUrl = currentPlayUrl,
                    initialPositionMs = initialPositionMs,
                )
            }
            val coroutineScope = rememberCoroutineScope()
            val completedNodeIds = remember(playbackEpisode.episodeId) { mutableStateListOf<String>() }
            var activeNode by remember(playbackEpisode.episodeId) { mutableStateOf<InteractionNode?>(null) }
            var submitResult by remember(playbackEpisode.episodeId) { mutableStateOf<InteractionSubmitResult?>(null) }
            var submitError by remember(playbackEpisode.episodeId) { mutableStateOf<String?>(null) }
            var isSubmitting by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var branchPlayback by remember(playbackEpisode.episodeId) { mutableStateOf<InteractionBranch?>(null) }
            var isFullscreen by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var isCleanPlayback by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(false) }
            var submittedNode by remember(playbackEpisode.episodeId) { mutableStateOf<InteractionNode?>(null) }
            var activeReactionClickCount by remember(playbackEpisode.episodeId) { mutableStateOf(0) }
            var historyRefreshTick by remember(playbackEpisode.episodeId) { mutableStateOf(0) }
            var playerPositionMs by remember(playbackEpisode.episodeId) { mutableStateOf(0L) }
            var playerDurationMs by remember(playbackEpisode.episodeId) { mutableStateOf(0L) }
            var playbackState by remember(playbackEpisode.episodeId) { mutableStateOf(Player.STATE_BUFFERING) }
            var playbackError by remember(playbackEpisode.episodeId) { mutableStateOf<String?>(null) }
            var playbackErrorCode by remember(playbackEpisode.episodeId) { mutableStateOf<String?>(null) }
            var playbackRetryCount by remember(playbackEpisode.episodeId) { mutableStateOf(0) }
            var playbackAttemptStartedAtMs by remember(playbackEpisode.episodeId) { mutableStateOf(0L) }
            var playbackAttemptReason by remember(playbackEpisode.episodeId) { mutableStateOf("initial") }
            var firstFrameReported by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var rebufferStartedAtMs by remember(playbackEpisode.episodeId) { mutableStateOf<Long?>(null) }
            var isPlaying by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var storyContinuationVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var storyContinuationState by remember(playbackEpisode.episodeId) {
                mutableStateOf<LoadState<AiStoryContinuationResult>?>(null)
            }
            var storyContinuationIntent by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf("") }
            var checkinCardVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var checkinCardState by remember(playbackEpisode.episodeId) {
                mutableStateOf<LoadState<AiCheckinCardResult>?>(null)
            }
            var selectedCheckinStyle by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf("short_drama_poster") }
            var checkinCardIntent by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf("") }
            var isStoryContinuationPlaying by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var moreMenuExpanded by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(false) }
            var resumeAfterMoreMenu by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var isLiked by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var progressBarVisible by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(false) }
            var safeAreaDebugVisible by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(false) }
            var commentPanelVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var resumeAfterCommentPanel by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var commentDraft by remember(playbackEpisode.episodeId) { mutableStateOf("") }
            var episodeIntroExpanded by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(false) }
            var quickSpeedActive by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var likeCount by rememberSaveable(playbackEpisode.episodeId) {
                mutableStateOf(seedEngagementCount(playbackEpisode.episodeId, 8200, 68000))
            }
            var shareCount by rememberSaveable(playbackEpisode.episodeId) {
                mutableStateOf(seedEngagementCount(playbackEpisode.episodeId, 1200, 9800))
            }
            var commentLikeRevision by remember(playbackEpisode.episodeId) { mutableStateOf(0) }
            var saveMomentMessage by remember(playbackEpisode.episodeId) { mutableStateOf<String?>(null) }
            var lastSavedMomentId by remember(playbackEpisode.episodeId) { mutableStateOf("") }
            var danmakuPanelVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var resumeAfterDanmakuPanel by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var danmakuDraft by remember(playbackEpisode.episodeId) { mutableStateOf("") }
            var danmakuFlowEnabled by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(true) }
            var danmakuAlpha by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(0.86f) }
            var danmakuSpeedMultiplier by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(1f) }
            var danmakuFontSizeSp by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(15f) }
            var danmakuAreaRatio by rememberSaveable(playbackEpisode.episodeId) { mutableStateOf(0.42f) }
            var danmakuLaneCursor by remember(playbackEpisode.episodeId) { mutableStateOf(0) }
            val danmakuItems = remember(playbackEpisode.episodeId) {
                mutableStateListOf<PlayerDanmakuEntry>().apply {
                    buildInitialDanmakuTexts(interactionConfig).forEachIndexed { index, text ->
                        add(
                            PlayerDanmakuEntry(
                                entryId = UUID.randomUUID().toString(),
                                text = text,
                                lane = index % PLAYER_DANMAKU_LANE_COUNT,
                                isUserGenerated = false,
                            )
                        )
                    }
                }
            }
            val commentItems = remember(playbackEpisode.episodeId) {
                mutableStateListOf(
                    "这段转场很像短视频爆点",
                    "主角气场压住全场了",
                    "下一秒就想看反击"
                )
            }
            var playbackInfoVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var playbackXRayVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var engagementVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var aiRecapVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            var aiRecapState by remember(playbackEpisode.episodeId) {
                mutableStateOf<LoadState<AiContentRecapResult>?>(null)
            }
            var playbackSpeed by remember(playbackEpisode.episodeId) { mutableStateOf(1f) }
            var autoPlayNextEpisode by remember(playbackEpisode.episodeId) { mutableStateOf(false) }
            val historyState by produceState<LoadState<List<InteractionLocalRecord>>>(
                initialValue = LoadState.Loading,
                playbackEpisode.episodeId,
                historyRefreshTick
            ) {
                value = try {
                    LoadState.Success(InteractionHistoryStore.load(context))
                } catch (throwable: Throwable) {
                    LoadState.Error(throwable.message ?: "互动记录加载失败")
                }
            }
            val insightsState by produceState<LoadState<InteractionInsights>>(
                initialValue = LoadState.Loading,
                playbackEpisode.episodeId,
                historyRefreshTick,
                resolvedRepository,
            ) {
                value = try {
                    LoadState.Success(resolvedRepository.loadInteractionInsights(playbackEpisode.episodeId))
                } catch (throwable: Throwable) {
                    LoadState.Error(throwable.message ?: "互动热力图加载失败")
                }
            }

            val episodeListState by produceState<LoadState<List<EpisodeCard>>>(
                initialValue = LoadState.Loading,
                interactionConfig.dramaId,
                resolvedRepository,
            ) {
                value = try {
                    LoadState.Success(resolvedRepository.loadEpisodes(interactionConfig.dramaId))
                } catch (throwable: Throwable) {
                    LoadState.Error(throwable.message ?: "选集加载失败")
                }
            }
            var episodePickerVisible by remember(playbackEpisode.episodeId) { mutableStateOf(false) }

            fun trackPlaybackBehavior(
                eventName: String,
                nodeId: String? = null,
                properties: Map<String, String> = emptyMap(),
            ) {
                coroutineScope.launch {
                    telemetryDispatcher.track(
                        context = context,
                        events = listOf(
                            playerBehaviorEvent(
                                eventName = eventName,
                                dramaId = interactionConfig.dramaId,
                                episodeId = playbackEpisode.episodeId,
                                nodeId = nodeId,
                                progressMs = playerPositionMs,
                                properties = properties,
                            )
                        )
                    )
                }
            }

            fun markPlaybackAttempt(reason: String, playUrl: String, resumePositionMs: Long = playerPositionMs) {
                playbackAttemptStartedAtMs = System.currentTimeMillis()
                playbackAttemptReason = reason
                firstFrameReported = false
                rebufferStartedAtMs = null
                trackPlaybackBehavior(
                    eventName = "video_start_attempt",
                    properties = mapOf(
                        "reason" to reason,
                        "playUrlType" to playbackUrlType(playUrl),
                        "resumePositionMs" to resumePositionMs.coerceAtLeast(0L).toString(),
                    ),
                )
            }

            fun retryPlaybackTracked(playUrl: String, resumePositionMs: Long, reason: String) {
                markPlaybackAttempt(reason, playUrl, resumePositionMs)
                retryPlaybackWithUrl(exoPlayer, playUrl, resumePositionMs)
            }

            fun switchToEpisode(targetEpisodeId: String, startMs: Long = 0L, reason: String) {
                if (targetEpisodeId.isBlank() || targetEpisodeId == playbackEpisode.episodeId) {
                    return
                }
                trackPlaybackBehavior(
                    eventName = "continue_watch",
                    properties = mapOf("mode" to reason),
                )
                episodePickerVisible = false
                onPlayEpisode(targetEpisodeId, startMs)
            }

            fun switchToNextEpisodeBySwipe() {
                val episodes = (episodeListState as? LoadState.Success<List<EpisodeCard>>)?.data.orEmpty()
                val nextEpisodeId = episodes
                    .sortedBy { it.episodeNo }
                    .let { sortedEpisodes ->
                        val currentIndex = sortedEpisodes.indexOfFirst { it.episodeId == playbackEpisode.episodeId }
                        sortedEpisodes.getOrNull(currentIndex + 1)?.episodeId
                    }
                    ?: resolveNextEpisodeId(playbackEpisode.episodeId)
                if (nextEpisodeId != null) {
                    switchToEpisode(nextEpisodeId, 0L, "swipe_next_episode")
                }
            }

            fun generateStoryContinuation() {
                if (storyContinuationState is LoadState.Loading) {
                    return
                }
                trackPlaybackBehavior(
                    eventName = "agnes_video_generate_start",
                    properties = mapOf("source" to "player"),
                )
                coroutineScope.launch {
                    storyContinuationState = LoadState.Loading
                    storyContinuationState = try {
                        val result = resolvedRepository.loadAiStoryContinuation(
                            episodeId = playbackEpisode.episodeId,
                            dramaId = interactionConfig.dramaId,
                            userIntent = storyContinuationIntent,
                            desiredEnding = storyContinuationIntent,
                            visualDirection = storyContinuationIntent,
                        )
                        val eventName = if (result.status == "ok" && result.degradeReason == null) {
                            "agnes_video_generate_success"
                        } else {
                            "agnes_video_generate_degraded"
                        }
                        trackPlaybackBehavior(
                            eventName = eventName,
                            properties = mapOf(
                                "provider" to result.providerName,
                                "status" to result.status,
                                "hasMedia" to result.mediaUrl.isNotBlank().toString(),
                                "latencyMs" to result.latencyMs.toString(),
                            ),
                        )
                        LoadState.Success(result)
                    } catch (throwable: Throwable) {
                        trackPlaybackBehavior(
                            eventName = "agnes_video_generate_degraded",
                            properties = mapOf(
                                "source" to "player",
                                "reason" to (throwable.message ?: "unknown"),
                            ),
                        )
                        LoadState.Error(throwable.message ?: "情节续写生成失败")
                    }
                }
            }

            fun generateCheckinCard(momentId: String = "", style: String = selectedCheckinStyle) {
                if (checkinCardState is LoadState.Loading) {
                    return
                }
                checkinCardVisible = true
                selectedCheckinStyle = style
                trackPlaybackBehavior(
                    eventName = "agnes_image_generate_start",
                    properties = mapOf(
                        "source" to "player",
                        "momentId" to momentId,
                        "style" to style,
                    ),
                )
                coroutineScope.launch {
                    checkinCardState = LoadState.Loading
                    checkinCardState = try {
                        val result = resolvedRepository.loadAiCheckinCard(
                            episodeId = playbackEpisode.episodeId,
                            dramaId = interactionConfig.dramaId,
                            momentId = momentId,
                            style = style,
                            userIntent = checkinCardIntent,
                            desiredEnding = checkinCardIntent,
                            visualDirection = checkinCardIntent,
                        )
                        val eventName = if (result.cardStatus == "ok" && result.cardDegradeReason.isBlank()) {
                            "agnes_image_generate_success"
                        } else {
                            "agnes_image_generate_degraded"
                        }
                        trackPlaybackBehavior(
                            eventName = eventName,
                            properties = mapOf(
                                "provider" to result.provider,
                                "status" to result.cardStatus,
                                "hasImage" to result.imageUrl.isNotBlank().toString(),
                                "latencyMs" to result.cardLatencyMs.toString(),
                                "momentId" to result.momentId,
                                "style" to result.style,
                            ),
                        )
                        LoadState.Success(result)
                    } catch (throwable: Throwable) {
                        trackPlaybackBehavior(
                            eventName = "agnes_image_generate_degraded",
                            properties = mapOf(
                                "source" to "player",
                                "reason" to (throwable.message ?: "unknown"),
                                "momentId" to momentId,
                                "style" to style,
                            ),
                        )
                        LoadState.Error(throwable.message ?: "打卡图生成失败")
                    }
                }
            }

            fun playStoryContinuation(result: AiStoryContinuationResult) {
                val playableUrl = result.mediaAsset.localUrl
                    .ifBlank { result.mediaAsset.mediaUrl }
                    .ifBlank { result.mediaUrl }
                if (playableUrl.isBlank()) {
                    return
                }
                storyContinuationVisible = false
                isStoryContinuationPlaying = true
                playbackError = null
                playbackErrorCode = null
                currentPlayUrl = playableUrl
                playerPositionMs = 0L
                trackPlaybackBehavior(
                    eventName = "continue_watch",
                    properties = mapOf("mode" to "story_continuation"),
                )
                retryPlaybackTracked(playableUrl, 0L, "story_continuation")
            }

            fun generateAiRecap() {
                if (aiRecapState is LoadState.Loading) {
                    return
                }
                coroutineScope.launch {
                    aiRecapState = LoadState.Loading
                    aiRecapState = try {
                        LoadState.Success(
                            resolvedRepository.loadAiContentRecap(
                                episodeId = playbackEpisode.episodeId,
                                dramaId = interactionConfig.dramaId,
                            )
                        )
                    } catch (throwable: Throwable) {
                        LoadState.Error(throwable.message ?: "剧情摘要生成失败")
                    }
                }
            }

            fun toggleLike() {
                likeCount += if (isLiked) -1 else 1
                isLiked = !isLiked
            }

            fun emitDanmaku(text: String, isUserGenerated: Boolean = true) {
                val content = text.trim().take(24)
                if (content.isBlank()) {
                    return
                }
                danmakuItems.add(
                    PlayerDanmakuEntry(
                        entryId = UUID.randomUUID().toString(),
                        text = content,
                        lane = danmakuLaneCursor % PLAYER_DANMAKU_LANE_COUNT,
                        isUserGenerated = isUserGenerated,
                    )
                )
                danmakuLaneCursor = (danmakuLaneCursor + 1) % PLAYER_DANMAKU_LANE_COUNT
                if (danmakuItems.size > PLAYER_DANMAKU_MAX_ACTIVE) {
                    danmakuItems.removeAt(0)
                }
            }

            fun submitComment() {
                val text = commentDraft.trim()
                if (text.isBlank()) {
                    return
                }
                commentItems.add(0, text)
                commentDraft = ""
            }

            fun submitDanmaku() {
                val text = danmakuDraft.trim()
                if (text.isBlank()) {
                    return
                }
                emitDanmaku(text, isUserGenerated = true)
                danmakuDraft = ""
                danmakuPanelVisible = false
                if (resumeAfterDanmakuPanel) {
                    exoPlayer.play()
                }
                resumeAfterDanmakuPanel = false
            }

            fun shareCurrentEpisode() {
                shareCount += 1
                val shareText = buildString {
                    append(playbackEpisode.title)
                    append(" · ")
                    append("当前进度 ")
                    append(formatPlaybackTime(playerPositionMs))
                    append("\n")
                    append(playbackEpisode.playUrl)
                }
                val sendIntent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_TEXT, shareText)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                runCatching {
                    context.startActivity(Intent.createChooser(sendIntent, "分享短剧"))
                }
            }

            fun copyCurrentLink() {
                clipboardManager.setText(AnnotatedString(currentPlayUrl))
            }

            fun nearestMomentNode(): InteractionNode? {
                activeNode?.let { return it }
                submittedNode?.let { return it }
                return interactionConfig.nodes.minByOrNull { node ->
                    abs(node.triggerMs - playerPositionMs)
                }?.takeIf { node ->
                    abs(node.triggerMs - playerPositionMs) <= 20_000L
                }
            }

            fun buildCurrentShareableMoment(): ShareableMoment {
                val node = nearestMomentNode()
                val startMs = maxOf((node?.triggerMs ?: playerPositionMs) - 8_000L, 0L)
                val endMs = maxOf((node?.triggerMs ?: playerPositionMs) + 16_000L, startMs + 6_000L)
                val episodeNo = Regex("""ep0*(\d+)""", RegexOption.IGNORE_CASE)
                    .find(playbackEpisode.episodeId)
                    ?.groupValues
                    ?.getOrNull(1)
                    ?.toIntOrNull()
                    ?: 0
                return ShareableMoment(
                    momentId = node?.let { "moment_${it.id}" } ?: "moment_${playbackEpisode.episodeId}_${playerPositionMs}",
                    dramaId = interactionConfig.dramaId,
                    episodeId = playbackEpisode.episodeId,
                    episodeNo = episodeNo,
                    episodeTitle = playbackEpisode.title,
                    startMs = startMs,
                    endMs = endMs,
                    title = node?.title ?: "当前进度高能片段",
                    hookText = node?.promptText ?: "从 ${formatPlaybackTime(startMs)} 开始回看这一段",
                    sourceNodeId = node?.id.orEmpty(),
                    source = node?.generationSource?.ifBlank { node.componentType } ?: "player_collect",
                    heatScore = ((node?.confidence ?: 0.62) * 100).toInt().coerceIn(40, 100),
                    playUrl = playbackEpisode.playUrl,
                )
            }

            fun saveCurrentMoment() {
                val moment = buildCurrentShareableMoment()
                coroutineScope.launch {
                    saveMomentMessage = "正在收藏高能片段"
                    saveMomentMessage = try {
                        val saved = resolvedRepository.saveShareableMoment(moment)
                        val savedNodeId = saved.sourceNodeId.takeIf { it.isNotBlank() }
                        trackPlaybackBehavior(
                            eventName = "moment_save",
                            nodeId = savedNodeId,
                            properties = mapOf(
                                "momentId" to saved.momentId,
                                "source" to saved.source,
                                "heatScore" to saved.heatScore.toString(),
                            ),
                        )
                        lastSavedMomentId = saved.momentId
                        "已收藏：${saved.title}"
                    } catch (throwable: Throwable) {
                        throwable.message ?: "收藏失败，请稍后重试"
                    }
                }
            }

            fun collapseActiveNode(node: InteractionNode? = activeNode, resumeIfHard: Boolean = false) {
                node?.let { completed ->
                    if (completed.id !in completedNodeIds) {
                        completedNodeIds += completed.id
                    }
                    if (resumeIfHard && completed.displayMode == "HARD" && !exoPlayer.isPlaying) {
                        exoPlayer.play()
                    }
                }
                activeNode = null
                activeReactionClickCount = 0
                submitError = null
            }

            LaunchedEffect(playbackEpisode.episodeId, danmakuFlowEnabled) {
                val autoPool = listOf(
                    "好帅",
                    "这段绝了",
                    "弹幕护体",
                    "反击要来了",
                    "直接起飞",
                    "这句有点狠",
                )
                var autoIndex = 0
                while (true) {
                    delay(6500)
                    if (!danmakuFlowEnabled || !isPlaying || playbackState != Player.STATE_READY) {
                        continue
                    }
                    emitDanmaku(autoPool[autoIndex % autoPool.size], isUserGenerated = false)
                    autoIndex += 1
                }
            }

            LaunchedEffect(playbackEpisode.episodeId, resolvedRepository) {
                telemetryDispatcher.track(
                    context = context,
                    events = listOf(
                        pageViewEvent(
                            screenName = "player",
                            dramaId = interactionConfig.dramaId,
                            episodeId = playbackEpisode.episodeId
                        )
                    )
                )
                markPlaybackAttempt("initial", currentPlayUrl, initialPositionMs)
            }

            LaunchedEffect(exoPlayer, playbackEpisode.episodeId) {
                while (true) {
                    delay(500)
                    playerPositionMs = exoPlayer.safePositionMs()
                    playerDurationMs = exoPlayer.safeDurationMs()
                }
            }

            LaunchedEffect(exoPlayer, playbackSpeed, quickSpeedActive) {
                exoPlayer.playbackParameters = PlaybackParameters(if (quickSpeedActive) 2f else playbackSpeed)
            }

            DisposableEffect(exoPlayer) {
                val listener = object : Player.Listener {
                    override fun onPlaybackStateChanged(playbackStateValue: Int) {
                        playbackState = playbackStateValue
                        if (playbackStateValue == Player.STATE_READY) {
                            playbackError = null
                            playbackErrorCode = null
                            val nowMs = System.currentTimeMillis()
                            val rebufferStart = rebufferStartedAtMs
                            if (!firstFrameReported && playbackAttemptStartedAtMs > 0L) {
                                firstFrameReported = true
                                trackPlaybackBehavior(
                                    eventName = "first_frame_rendered",
                                    properties = mapOf(
                                        "startupMs" to (nowMs - playbackAttemptStartedAtMs).coerceAtLeast(0L).toString(),
                                        "reason" to playbackAttemptReason,
                                        "playUrlType" to playbackUrlType(currentPlayUrl),
                                        "durationMs" to exoPlayer.safeDurationMs().coerceAtLeast(0L).toString(),
                                    ),
                                )
                            } else if (rebufferStart != null) {
                                rebufferStartedAtMs = null
                                trackPlaybackBehavior(
                                    eventName = "rebuffer_end",
                                    properties = mapOf(
                                        "durationMs" to (nowMs - rebufferStart).coerceAtLeast(0L).toString(),
                                        "playUrlType" to playbackUrlType(currentPlayUrl),
                                        "playerState" to playbackStateValue.toString(),
                                    ),
                                )
                            }
                        } else if (
                            playbackStateValue == Player.STATE_BUFFERING &&
                            firstFrameReported &&
                            rebufferStartedAtMs == null
                        ) {
                            rebufferStartedAtMs = System.currentTimeMillis()
                            trackPlaybackBehavior(
                                eventName = "rebuffer_start",
                                properties = mapOf(
                                    "playUrlType" to playbackUrlType(currentPlayUrl),
                                    "positionMs" to exoPlayer.safePositionMs().coerceAtLeast(0L).toString(),
                                ),
                            )
                        }
                        if (playbackStateValue == Player.STATE_ENDED && branchPlayback == null && !isStoryContinuationPlaying) {
                            isStoryContinuationPlaying = false
                            val nextEpisodeId = resolveNextEpisodeId(playbackEpisode.episodeId)
                            if (autoPlayNextEpisode && nextEpisodeId != null) {
                                trackPlaybackBehavior(
                                    eventName = "continue_watch",
                                    properties = mapOf("mode" to "auto_next_episode"),
                                )
                                onPlayEpisode(nextEpisodeId, 0L)
                            } else {
                                storyContinuationVisible = true
                            }
                        }
                    }

                    override fun onIsPlayingChanged(isPlayingValue: Boolean) {
                        isPlaying = isPlayingValue
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        playbackError = error.message ?: "视频播放失败，请重试"
                        playbackErrorCode = error.errorCodeName
                        trackPlaybackBehavior(
                            eventName = "playback_error",
                            nodeId = branchPlayback?.segmentId,
                            properties = mapOf(
                                "errorCode" to error.errorCodeName,
                                "isBranchPlayback" to (branchPlayback != null).toString(),
                                "playUrlType" to playbackUrlType(currentPlayUrl),
                                "firstFrameRendered" to firstFrameReported.toString(),
                                "startupMs" to (System.currentTimeMillis() - playbackAttemptStartedAtMs)
                                    .coerceAtLeast(0L)
                                    .toString(),
                            ),
                        )
                        val activeBranch = branchPlayback
                        if (activeBranch != null && currentPlayUrl != mainPlayUrl) {
                            currentPlayUrl = mainPlayUrl
                            retryPlaybackTracked(mainPlayUrl, activeBranch.returnSeekMs, "branch_return_after_error")
                            branchPlayback = null
                            return
                        }
                        if (isStoryContinuationPlaying) {
                            isStoryContinuationPlaying = false
                            storyContinuationVisible = true
                            return
                        }
                        if (currentPlayUrl == playbackEpisode.hlsUrl && playbackEpisode.playUrl.isNotBlank()) {
                            currentPlayUrl = playbackEpisode.playUrl
                            retryPlaybackTracked(playbackEpisode.playUrl, playerPositionMs, "hls_fallback_mp4")
                        }
                    }
                }
                exoPlayer.addListener(listener)
                onDispose {
                    if (!firstFrameReported && playbackAttemptStartedAtMs > 0L) {
                        trackPlaybackBehavior(
                            eventName = "exit_before_start",
                            properties = mapOf(
                                "reason" to playbackAttemptReason,
                                "playUrlType" to playbackUrlType(currentPlayUrl),
                                "startupMs" to (System.currentTimeMillis() - playbackAttemptStartedAtMs)
                                    .coerceAtLeast(0L)
                                    .toString(),
                            ),
                        )
                    }
                    exoPlayer.removeListener(listener)
                    exoPlayer.clearVideoSurface()
                    exoPlayer.release()
                }
            }

            LaunchedEffect(exoPlayer, playbackEpisode.episodeId, interactionConfig.dramaId) {
                while (true) {
                    delay(5000)
                    if (branchPlayback != null || isStoryContinuationPlaying) {
                        continue
                    }
                    val durationMs = exoPlayer.safeDurationMs()
                    if (durationMs <= 0L) {
                        continue
                    }
                    val progressMs = exoPlayer.safePositionMs()
                    runCatching {
                        resolvedRepository.reportWatchProgress(
                            dramaId = interactionConfig.dramaId,
                            episodeId = playbackEpisode.episodeId,
                            progressMs = progressMs,
                            durationMs = durationMs,
                            isCompleted = progressMs >= durationMs - 1000L
                        )
                    }
                }
            }

            LaunchedEffect(exoPlayer, interactionConfig.nodes, activeNode, submitResult, branchPlayback) {
                while (true) {
                    delay(500)
                    val currentBranch = branchPlayback
                    if (currentBranch != null) {
                        val currentPositionMs = exoPlayer.safePositionMs()
                        if (currentPositionMs >= currentBranch.endMs) {
                            trackPlaybackBehavior(
                                eventName = "insert_play_complete",
                                nodeId = currentBranch.segmentId,
                                properties = mapOf("segmentId" to currentBranch.segmentId),
                            )
                            branchPlayback = null
                            currentPlayUrl = mainPlayUrl
                            playerPositionMs = currentBranch.returnSeekMs
                            retryPlaybackTracked(mainPlayUrl, currentBranch.returnSeekMs, "branch_return")
                        }
                        continue
                    }

                    if (isStoryContinuationPlaying) {
                        continue
                    }

                    if (activeNode != null || submitResult != null) {
                        continue
                    }

                    val currentPositionMs = exoPlayer.safePositionMs()
                    val nextNode = interactionConfig.nodes.firstOrNull { node ->
                        node.id !in completedNodeIds &&
                            currentPositionMs >= node.triggerMs &&
                            currentPositionMs <= node.triggerMs + 1_500L
                    }
                    if (nextNode != null) {
                        submitError = null
                        activeNode = nextNode
                        activeReactionClickCount = 0
                        if (nextNode.displayMode == "HARD") {
                            exoPlayer.pause()
                        }
                    }
                }
            }

            LaunchedEffect(activeNode?.id) {
                val node = activeNode ?: return@LaunchedEffect
                telemetryDispatcher.track(
                    context = context,
                    events = listOf(
                        interactionImpressionEvent(
                            dramaId = interactionConfig.dramaId,
                            episodeId = interactionConfig.episodeId,
                            node = node,
                        )
                    )
                )
                val timeoutMs = node.timeoutMs.takeIf { it > 0L }?.coerceIn(5_000L, 10_000L) ?: 7_000L
                delay(timeoutMs)
                if (activeNode?.id == node.id) {
                    collapseActiveNode(node, resumeIfHard = true)
                }
            }

            LaunchedEffect(saveMomentMessage) {
                val message = saveMomentMessage ?: return@LaunchedEffect
                if (!message.startsWith("正在")) {
                    delay(2400)
                    if (saveMomentMessage == message) {
                        saveMomentMessage = null
                    }
                }
            }

            fun submitReactionClick(node: InteractionNode) {
                activeReactionClickCount += 1
                if (activeReactionClickCount > 1 || node.id in completedNodeIds) {
                    return
                }
                val option = node.options.firstOrNull() ?: return
                completedNodeIds += node.id
                coroutineScope.launch {
                    isSubmitting = true
                    submitError = null
                    try {
                        trackPlaybackBehavior(
                            eventName = "interaction_component_click",
                            nodeId = node.id,
                            properties = interactionComponentProperties(node, option),
                        )
                        val result = resolvedRepository.submitInteraction(
                            dramaId = interactionConfig.dramaId,
                            episodeId = interactionConfig.episodeId,
                            node = node,
                            option = option,
                        )
                        telemetryDispatcher.track(
                            context = context,
                            events = listOf(
                                interactionSubmitEvent(
                                    dramaId = interactionConfig.dramaId,
                                    episodeId = interactionConfig.episodeId,
                                    nodeId = node.id,
                                    optionId = option.id,
                                    optionText = option.text,
                                    nextActionType = result.nextActionType,
                                    branchSegmentId = null,
                                    componentType = node.componentType,
                                    visualStyle = node.visualStyle,
                                    analyticsKey = node.analyticsKey,
                                )
                            )
                        )
                        InteractionHistoryStore.append(
                            context = context,
                            record = InteractionLocalRecord(
                                recordId = result.recordId,
                                dramaId = interactionConfig.dramaId,
                                episodeId = interactionConfig.episodeId,
                                nodeId = node.id,
                                nodeTitle = node.title,
                                optionId = option.id,
                                optionText = option.text,
                                feedbackText = result.feedbackText,
                                nextActionType = result.nextActionType,
                                branchSegmentId = null,
                                recordedAtMs = System.currentTimeMillis(),
                            )
                        )
                        historyRefreshTick += 1
                    } catch (throwable: Throwable) {
                        submitError = throwable.message ?: "提交失败，请重试"
                    } finally {
                        isSubmitting = false
                    }
                }
            }

            fun submitInteractionFromNode(node: InteractionNode, option: InteractionOption) {
                coroutineScope.launch {
                    isSubmitting = true
                    submitError = null
                    try {
                        val branch = option.branch
                        trackPlaybackBehavior(
                            eventName = "interaction_component_click",
                            nodeId = node.id,
                            properties = interactionComponentProperties(node, option),
                        )
                        val result = resolvedRepository.submitInteraction(
                            dramaId = interactionConfig.dramaId,
                            episodeId = interactionConfig.episodeId,
                            node = node,
                            option = option,
                        )
                        telemetryDispatcher.track(
                            context = context,
                            events = listOf(
                                interactionSubmitEvent(
                                    dramaId = interactionConfig.dramaId,
                                    episodeId = interactionConfig.episodeId,
                                    nodeId = node.id,
                                    optionId = option.id,
                                    optionText = option.text,
                                    nextActionType = result.nextActionType,
                                    branchSegmentId = branch?.segmentId,
                                    componentType = node.componentType,
                                    visualStyle = node.visualStyle,
                                    analyticsKey = node.analyticsKey,
                                )
                            )
                        )
                        InteractionHistoryStore.append(
                            context = context,
                            record = InteractionLocalRecord(
                                recordId = result.recordId,
                                dramaId = interactionConfig.dramaId,
                                episodeId = interactionConfig.episodeId,
                                nodeId = node.id,
                                nodeTitle = node.title,
                                optionId = option.id,
                                optionText = option.text,
                                feedbackText = result.feedbackText,
                                nextActionType = result.nextActionType,
                                branchSegmentId = branch?.segmentId,
                                recordedAtMs = System.currentTimeMillis(),
                            )
                        )
                        historyRefreshTick += 1
                        if (node.visualStyle == "弹幕冲浪") {
                            emitDanmaku(
                                option.text.ifBlank {
                                    node.effectText.ifBlank { node.title }
                                },
                                isUserGenerated = false,
                            )
                        }
                        completedNodeIds += node.id
                        activeNode = null
                        submittedNode = node
                        submitResult = result
                        if (branch != null && branch.mediaUrl.isNotBlank()) {
                            currentPlayUrl = branch.mediaUrl.ifBlank { mainPlayUrl }
                            playerPositionMs = branch.startMs.coerceAtLeast(0L)
                            playbackError = null
                            playbackErrorCode = null
                            branchPlayback = branch
                            trackPlaybackBehavior(
                                eventName = "insert_play_start",
                                nodeId = node.id,
                                properties = mapOf("segmentId" to branch.segmentId),
                            )
                            retryPlaybackTracked(currentPlayUrl, branch.startMs, "aigc_insert")
                        } else if (node.displayMode == "HARD") {
                            exoPlayer.play()
                        }
                    } catch (throwable: Throwable) {
                        submitError = throwable.message ?: "提交失败，请重试"
                    } finally {
                        isSubmitting = false
                    }
                }
            }

            fun retryPlayback() {
                playbackRetryCount += 1
                playbackError = null
                playbackErrorCode = null
                retryPlaybackTracked(currentPlayUrl, playerPositionMs, "manual_retry")
            }

            fun exitFullscreen() {
                trackPlaybackBehavior(eventName = "fullscreen_exit")
                isFullscreen = false
            }

            fun openMoreActionSheet() {
                resumeAfterMoreMenu = exoPlayer.isPlaying
                if (resumeAfterMoreMenu) {
                    exoPlayer.pause()
                }
                moreMenuExpanded = true
            }

            fun closeMoreActionSheet(resumeIfNeeded: Boolean = true) {
                moreMenuExpanded = false
                if (resumeIfNeeded && resumeAfterMoreMenu) {
                    exoPlayer.play()
                }
                resumeAfterMoreMenu = false
            }

            fun openCommentPanel() {
                resumeAfterCommentPanel = exoPlayer.isPlaying
                if (resumeAfterCommentPanel) {
                    exoPlayer.pause()
                }
                commentPanelVisible = true
            }

            fun closeCommentPanel() {
                commentPanelVisible = false
                if (resumeAfterCommentPanel) {
                    exoPlayer.play()
                }
                resumeAfterCommentPanel = false
            }

            fun openDanmakuPanel() {
                resumeAfterDanmakuPanel = exoPlayer.isPlaying
                if (resumeAfterDanmakuPanel) {
                    exoPlayer.pause()
                }
                danmakuPanelVisible = true
            }

            fun closeDanmakuPanel() {
                danmakuPanelVisible = false
                if (resumeAfterDanmakuPanel) {
                    exoPlayer.play()
                }
                resumeAfterDanmakuPanel = false
            }

            BackHandler(enabled = isCleanPlayback) {
                isCleanPlayback = false
            }

            BackHandler(enabled = isFullscreen) {
                exitFullscreen()
            }

            Scaffold(
                containerColor = Color.Black
            ) { padding ->
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                ) {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(0.dp),
                    ) {
                        item {
                            BoxWithConstraints(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .fillParentMaxHeight()
                                    .background(Color.Black)
                            ) {
                                ShortPlayVideoSurface(
                                    exoPlayer = exoPlayer,
                                    playbackState = playbackState,
                                    modifier = Modifier.fillMaxSize(),
                                )

                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .playerTapAndSwipeGesture(
                                            onTap = {
                                                if (isCleanPlayback) {
                                                    isCleanPlayback = false
                                                } else if (exoPlayer.isPlaying) {
                                                    exoPlayer.pause()
                                                } else {
                                                    exoPlayer.play()
                                                }
                                            },
                                            onSwipeUp = { switchToNextEpisodeBySwipe() },
                                        )
                                )

                                PlayerQuickSpeedEdgeLayer(
                                    enabled = !isCleanPlayback,
                                    onQuickSpeedStart = {
                                        quickSpeedActive = true
                                        if (!exoPlayer.isPlaying) {
                                            exoPlayer.play()
                                        }
                                    },
                                    onQuickSpeedEnd = { quickSpeedActive = false },
                                    modifier = Modifier.fillMaxSize(),
                                )

                                if (quickSpeedActive) {
                                    Surface(
                                        modifier = Modifier
                                            .align(Alignment.TopCenter)
                                            .padding(top = 54.dp),
                                        shape = RoundedCornerShape(999.dp),
                                        color = Color.Black.copy(alpha = 0.24f),
                                    ) {
                                        Text(
                                            text = "2.0x",
                                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 7.dp),
                                            color = Color.White,
                                            style = MaterialTheme.typography.titleMedium,
                                            fontWeight = FontWeight.Bold,
                                        )
                                    }
                                }

                                if (!isCleanPlayback) {
                                    IconButton(
                                        onClick = onBack,
                                        modifier = Modifier
                                            .align(Alignment.TopStart)
                                            .padding(8.dp)
                                    ) {
                                    Icon(
                                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                        contentDescription = "返回",
                                        tint = Color.White,
                                    )
                                    }
                                }

                                if (!isPlaying && playbackState == Player.STATE_READY &&
                                    activeNode == null && submitResult == null
                                ) {
                                    Surface(
                                        modifier = Modifier
                                            .align(Alignment.Center)
                                            .clickable { exoPlayer.play() },
                                        shape = CircleShape,
                                        color = Color.Black.copy(alpha = 0.18f),
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.PlayArrow,
                                            contentDescription = "播放",
                                            modifier = Modifier
                                                .padding(16.dp)
                                                .size(36.dp)
                                                .alpha(0.72f),
                                            tint = Color.White,
                                        )
                                    }
                                }

                                if (progressBarVisible && !isCleanPlayback) {
                                    Surface(
                                        modifier = Modifier
                                            .align(Alignment.BottomCenter)
                                            .fillMaxWidth(),
                                        color = Color.Black.copy(alpha = 0.20f),
                                    ) {
                                        CompactPlaybackProgress(
                                            positionMs = playerPositionMs,
                                            durationMs = playerDurationMs,
                                            onSeekTo = { targetMs ->
                                                playerPositionMs = targetMs
                                                exoPlayer.seekTo(targetMs)
                                            },
                                        )
                                    }
                                }

                                if (!isCleanPlayback) {
                                    PlayerEpisodePickerBar(
                                        playbackEpisode = playbackEpisode,
                                        episodes = (episodeListState as? LoadState.Success<List<EpisodeCard>>)?.data.orEmpty(),
                                        progressMs = playerPositionMs,
                                        durationMs = playerDurationMs,
                                        onClick = { episodePickerVisible = true },
                                        modifier = Modifier
                                            .align(Alignment.BottomCenter)
                                            .padding(
                                                start = 76.dp,
                                                end = 76.dp,
                                                bottom = if (progressBarVisible) 34.dp else 10.dp,
                                            ),
                                    )
                                }

                                PlayerDanmakuStreamOverlay(
                                    entries = danmakuItems,
                                    enabled = danmakuFlowEnabled && !isFullscreen && !isCleanPlayback,
                                    modifier = Modifier.fillMaxSize(),
                                    alpha = danmakuAlpha,
                                    speedMultiplier = danmakuSpeedMultiplier,
                                    fontSizeSp = danmakuFontSizeSp,
                                    areaRatio = danmakuAreaRatio,
                                    onConsumed = { entryId ->
                                        danmakuItems.removeAll { it.entryId == entryId }
                                    },
                                )

                                if (!isCleanPlayback) {
                                    IconButton(
                                        onClick = { openMoreActionSheet() },
                                        modifier = Modifier.align(Alignment.TopEnd)
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.MoreVert,
                                            contentDescription = "更多",
                                            tint = Color.White,
                                        )
                                    }
                                }

                                if (!isCleanPlayback) {
                                    Column(
                                        modifier = Modifier
                                            .align(Alignment.BottomEnd)
                                        .padding(
                                            end = 10.dp,
                                            bottom = if (progressBarVisible) 52.dp else 20.dp,
                                        ),
                                    verticalArrangement = Arrangement.spacedBy(14.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                ) {
                                    PlayerActionIcon(
                                        icon = Icons.Default.Favorite,
                                        description = if (isLiked) "已赞" else "点赞",
                                        tint = if (isLiked) Color(0xFFFF5F88) else Color.White,
                                        countLabel = formatCompactCount(likeCount),
                                        onClick = { toggleLike() },
                                    )
                                    PlayerActionIcon(
                                        icon = Icons.Default.ChatBubble,
                                        description = "评论",
                                        tint = Color.White,
                                        countLabel = formatCompactCount(commentItems.size + 1280),
                                        onClick = { openCommentPanel() },
                                    )
                                    PlayerActionIcon(
                                        icon = Icons.Default.Share,
                                        description = "分享",
                                        tint = Color.White,
                                        countLabel = formatCompactCount(shareCount),
                                        onClick = { shareCurrentEpisode() },
                                    )
                                    PlayerDanmakuFloatingButton(
                                        onClick = { openDanmakuPanel() },
                                    )
                                }
                                }

                                if (!isCleanPlayback) {
                                PlayerEpisodeTextOverlay(
                                    title = playbackEpisode.title,
                                    intro = buildPlayerEpisodeIntro(
                                        playbackEpisode = playbackEpisode,
                                        interactionConfig = interactionConfig,
                                        episodeSummary = current.data.episodeSummary,
                                    ),
                                        expanded = episodeIntroExpanded,
                                        onToggleExpanded = { episodeIntroExpanded = !episodeIntroExpanded },
                                        modifier = Modifier
                                            .align(Alignment.BottomStart)
                                            .padding(
                                                start = 16.dp,
                                                end = 96.dp,
                                                bottom = if (progressBarVisible) 68.dp else 24.dp,
                                            ),
                                    )
                                }

                                if (playbackError != null) {
                                    Card(
                                        modifier = Modifier
                                            .align(Alignment.BottomCenter)
                                            .padding(12.dp),
                                        shape = RoundedCornerShape(20.dp),
                                        colors = CardDefaults.cardColors(
                                            containerColor = MaterialTheme.colorScheme.errorContainer
                                        )
                                    ) {
                                        Column(
                                            modifier = Modifier.padding(12.dp),
                                            verticalArrangement = Arrangement.spacedBy(8.dp)
                                        ) {
                                            Text(
                                                text = playbackError.orEmpty(),
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = MaterialTheme.colorScheme.onErrorContainer,
                                            )
                                            TextButton(
                                                onClick = { retryPlayback() },
                                            ) {
                                                Text(text = "重试播放")
                                            }
                                        }
                                    }
                                }

                                if (safeAreaDebugVisible) {
                                    PlayerSafeAreaDebugLayer(
                                        progressVisible = progressBarVisible,
                                        danmakuVisible = danmakuFlowEnabled,
                                        activeNode = activeNode,
                                        modifier = Modifier.fillMaxSize(),
                                    )
                                }

                                saveMomentMessage?.let { message ->
                                    Surface(
                                        modifier = Modifier
                                            .align(Alignment.BottomCenter)
                                            .padding(bottom = if (progressBarVisible) 86.dp else 54.dp),
                                        shape = RoundedCornerShape(999.dp),
                                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.94f),
                                        tonalElevation = 6.dp,
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                        ) {
                                            Text(
                                                text = message,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onPrimaryContainer,
                                            )
                                            if (message.startsWith("已收藏")) {
                                                TextButton(
                                                    onClick = { generateCheckinCard(lastSavedMomentId, "face_slap") },
                                                ) {
                                                    Text(text = "生成同款打卡图")
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                    }

                    if (commentPanelVisible) {
                        PlayerCommentsSheet(
                            comments = commentItems,
                            draft = commentDraft,
                            revision = commentLikeRevision,
                            onDraftChange = { commentDraft = it },
                            onCommentLike = { commentLikeRevision += 1 },
                            onCommentDislike = { commentLikeRevision += 1 },
                            onReply = { author -> commentDraft = "回复@$author " },
                            onSend = { submitComment() },
                            onDismiss = { closeCommentPanel() },
                        )
                    }

                    if (playbackInfoVisible) {
                        PlayerPlaybackInfoDialog(
                            playbackState = playbackState,
                            isPlaying = isPlaying,
                            playUrl = playbackEpisode.playUrl,
                            currentPlayUrl = currentPlayUrl,
                            isBranchPlayback = branchPlayback != null,
                            hlsAvailable = playbackEpisode.hlsAvailable,
                            positionMs = playerPositionMs,
                            durationMs = playerDurationMs,
                            retryCount = playbackRetryCount,
                            errorCode = playbackErrorCode,
                            errorMessage = playbackError,
                            onRetry = { retryPlayback() },
                            onDismiss = { playbackInfoVisible = false },
                        )
                    }

                    if (playbackXRayVisible) {
                        PlayerStoryXRayDialog(
                            interactionConfig = interactionConfig,
                            positionMs = playerPositionMs,
                            onSeekTo = { targetMs ->
                                playerPositionMs = targetMs
                                exoPlayer.seekTo(targetMs)
                            },
                            onDismiss = { playbackXRayVisible = false },
                        )
                    }

                    if (danmakuPanelVisible) {
                        PlayerDanmakuSheet(
                            draft = danmakuDraft,
                            alpha = danmakuAlpha,
                            speedMultiplier = danmakuSpeedMultiplier,
                            fontSizeSp = danmakuFontSizeSp,
                            areaRatio = danmakuAreaRatio,
                            onDraftChange = { danmakuDraft = it },
                            onAlphaChange = { danmakuAlpha = it },
                            onSpeedChange = { danmakuSpeedMultiplier = it },
                            onFontSizeChange = { danmakuFontSizeSp = it },
                            onAreaRatioChange = { danmakuAreaRatio = it },
                            onSend = { submitDanmaku() },
                            onDismiss = { closeDanmakuPanel() },
                        )
                    }

                    if (episodePickerVisible) {
                        PlayerEpisodePickerSheet(
                            episodes = (episodeListState as? LoadState.Success<List<EpisodeCard>>)?.data.orEmpty(),
                            currentEpisodeId = playbackEpisode.episodeId,
                            onEpisodeClick = { episode ->
                                switchToEpisode(episode.episodeId, 0L, "episode_picker")
                            },
                            onDismiss = { episodePickerVisible = false },
                        )
                    }

                    if (aiRecapVisible) {
                        PlayerAiRecapDialog(
                            episodeTitle = playbackEpisode.title,
                            state = aiRecapState,
                            onGenerate = { generateAiRecap() },
                            onDismiss = { aiRecapVisible = false },
                        )
                    }

                    if (engagementVisible) {
                        PlayerEngagementDialog(
                            insightsState = insightsState,
                            historyState = historyState,
                            onSeekTo = { targetMs ->
                                playerPositionMs = targetMs
                                exoPlayer.seekTo(targetMs)
                            },
                            onDismiss = { engagementVisible = false },
                        )
                    }

                    PlayerMoreActionSheet(
                        visible = moreMenuExpanded,
                        themeMode = themeMode,
                        playbackSpeed = playbackSpeed,
                        progressBarVisible = progressBarVisible,
                        autoPlayNextEpisode = autoPlayNextEpisode,
                        safeAreaDebugVisible = safeAreaDebugVisible,
                        onDismiss = { closeMoreActionSheet() },
                        onToggleTheme = {
                            closeMoreActionSheet()
                            onToggleTheme()
                        },
                        onOpenAiRecap = {
                            closeMoreActionSheet(resumeIfNeeded = false)
                            aiRecapVisible = true
                            if (aiRecapState !is LoadState.Success && aiRecapState !is LoadState.Loading) {
                                generateAiRecap()
                            }
                        },
                        onOpenPlaybackInfo = {
                            closeMoreActionSheet(resumeIfNeeded = false)
                            playbackInfoVisible = true
                        },
                        onOpenXRay = {
                            closeMoreActionSheet(resumeIfNeeded = false)
                            playbackXRayVisible = true
                        },
                        onToggleProgress = {
                            closeMoreActionSheet()
                            progressBarVisible = !progressBarVisible
                        },
                        onOpenEngagement = {
                            closeMoreActionSheet(resumeIfNeeded = false)
                            engagementVisible = true
                        },
                        onSaveMoment = {
                            closeMoreActionSheet()
                            saveCurrentMoment()
                        },
                        onToggleAutoPlayNext = {
                            closeMoreActionSheet()
                            autoPlayNextEpisode = !autoPlayNextEpisode
                        },
                        onCopyLink = {
                            closeMoreActionSheet()
                            copyCurrentLink()
                        },
                        onCleanPlayback = {
                            closeMoreActionSheet(resumeIfNeeded = false)
                            isCleanPlayback = true
                            exoPlayer.play()
                        },
                        onSpeedSelected = { speed ->
                            playbackSpeed = speed
                        },
                        onToggleSafeAreaDebug = {
                            closeMoreActionSheet()
                            safeAreaDebugVisible = !safeAreaDebugVisible
                        },
                    )

                    activeNode?.let { node ->
                        InteractionOverlay(
                            modifier = Modifier
                                .align(interactionOverlayAlignment(node))
                                .interactionSafePadding(
                                    node = node,
                                    progressVisible = progressBarVisible,
                                    danmakuVisible = danmakuFlowEnabled,
                                ),
                            node = node,
                            isSubmitting = isSubmitting,
                            submitError = submitError,
                            reactionClickCount = activeReactionClickCount,
                            onReactionClick = { submitReactionClick(node) },
                            onOptionSelected = { option -> submitInteractionFromNode(node, option) },
                            onSkip = {
                                trackPlaybackBehavior(
                                    eventName = "interaction_component_skip",
                                    nodeId = node.id,
                                    properties = interactionComponentProperties(node),
                                )
                                collapseActiveNode(node, resumeIfHard = true)
                            }
                        )
                    }

                    submitResult?.let { result ->
                        FeedbackOverlay(
                            modifier = Modifier.align(feedbackOverlayAlignment(submittedNode)),
                            result = result,
                            node = submittedNode,
                            onDismiss = {
                                submitResult = null
                                submittedNode = null
                            }
                        )
                    }

                    if (storyContinuationVisible && !isFullscreen) {
                        StoryContinuationOverlay(
                            modifier = Modifier.align(Alignment.Center),
                            state = storyContinuationState,
                            userIntent = storyContinuationIntent,
                            onUserIntentChange = {
                                storyContinuationIntent = it
                                storyContinuationState = null
                            },
                            onGenerate = { generateStoryContinuation() },
                            onPlay = { result -> playStoryContinuation(result) },
                            onGenerateCheckin = { generateCheckinCard(style = "reversal_scene") },
                            onDismiss = { storyContinuationVisible = false },
                        )
                    }

                    if (checkinCardVisible && !isFullscreen) {
                        CheckinCardOverlay(
                            modifier = Modifier.align(Alignment.Center),
                            state = checkinCardState,
                            selectedStyle = selectedCheckinStyle,
                            userIntent = checkinCardIntent,
                            onUserIntentChange = {
                                checkinCardIntent = it
                                checkinCardState = null
                            },
                            onStyleSelected = {
                                selectedCheckinStyle = it
                                checkinCardState = null
                            },
                            onGenerate = { generateCheckinCard(style = selectedCheckinStyle) },
                            onDismiss = { checkinCardVisible = false },
                        )
                    }

                    if (isFullscreen) {
                        FullscreenPlayerDialog(
                            exoPlayer = exoPlayer,
                            playbackState = playbackState,
                            isPlaying = isPlaying,
                            positionMs = playerPositionMs,
                            durationMs = playerDurationMs,
                            progressVisible = progressBarVisible,
                            danmakuEntries = danmakuItems,
                            danmakuFlowEnabled = danmakuFlowEnabled,
                            onDanmakuConsumed = { entryId ->
                                danmakuItems.removeAll { it.entryId == entryId }
                            },
                            activeNode = activeNode,
                            submitResult = submitResult,
                            submittedNode = submittedNode,
                            reactionClickCount = activeReactionClickCount,
                            isSubmitting = isSubmitting,
                            submitError = submitError,
                            storyContinuationVisible = storyContinuationVisible,
                            storyContinuationState = storyContinuationState,
                            checkinCardVisible = checkinCardVisible,
                            checkinCardState = checkinCardState,
                            onExitFullscreen = { exitFullscreen() },
                            onSeekTo = { targetMs ->
                                playerPositionMs = targetMs
                                exoPlayer.seekTo(targetMs)
                            },
                            onPlayPause = {
                                if (exoPlayer.isPlaying) {
                                    exoPlayer.pause()
                                } else {
                                    exoPlayer.play()
                                }
                            },
                            onReactionClick = { node -> submitReactionClick(node) },
                            onOptionSelected = { node, option -> submitInteractionFromNode(node, option) },
                            onSkipNode = { node ->
                                trackPlaybackBehavior(
                                    eventName = "interaction_component_skip",
                                    nodeId = node.id,
                                    properties = interactionComponentProperties(node),
                                )
                                collapseActiveNode(node, resumeIfHard = true)
                            },
                            onDismissFeedback = {
                                submitResult = null
                                submittedNode = null
                            },
                            onGenerateStoryContinuation = { generateStoryContinuation() },
                            onPlayStoryContinuation = { result -> playStoryContinuation(result) },
                            onDismissStoryContinuation = { storyContinuationVisible = false },
                            onGenerateCheckinCard = { generateCheckinCard(style = selectedCheckinStyle) },
                            onDismissCheckinCard = { checkinCardVisible = false },
                            selectedCheckinStyle = selectedCheckinStyle,
                            onCheckinStyleSelected = {
                                selectedCheckinStyle = it
                                checkinCardState = null
                            },
                            safeAreaDebugVisible = safeAreaDebugVisible,
                        )
                    }
                }
            }

        }
    }
}
@Composable
private fun ShortPlayVideoSurface(
    exoPlayer: ExoPlayer,
    playbackState: Int,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier.background(Color.Black)
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { viewContext ->
                TextureView(viewContext).apply {
                    exoPlayer.setVideoTextureView(this)
                }
            },
            update = { textureView ->
                exoPlayer.setVideoTextureView(textureView)
            }
        )
        if (playbackState == Player.STATE_BUFFERING) {
            CircularProgressIndicator(
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(28.dp),
                color = Color.White,
            )
        }
    }
}

@Composable
private fun AigcInsertClipPreview(
    mediaUrl: String,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .background(Color(0xFF1C1630), RoundedCornerShape(20.dp))
            .border(1.dp, Color(0xFF6D53E0), RoundedCornerShape(20.dp))
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "AIGC 插片预览",
                    style = MaterialTheme.typography.titleSmall,
                    color = Color.White,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "点击后会替换当前视频播放，播完自动回到主线节点。",
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFFE2DBFF),
                )
                Text(
                    text = mediaUrl.ifBlank { "插片地址生成中" },
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFB8AAFF),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Surface(shape = RoundedCornerShape(999.dp), color = Color(0x33FFFFFF)) {
                    Text(
                        text = "替换主视频",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White,
                    )
                }
                Surface(shape = RoundedCornerShape(999.dp), color = Color(0x33FFFFFF)) {
                    Text(
                        text = "播完回主线",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = Color.White,
                    )
                }
            }
        }
    }
}

@Composable
private fun FullscreenPlayerDialog(
    exoPlayer: ExoPlayer,
    playbackState: Int,
    isPlaying: Boolean,
    positionMs: Long,
    durationMs: Long,
    progressVisible: Boolean,
    danmakuEntries: List<PlayerDanmakuEntry>,
    danmakuFlowEnabled: Boolean,
    onDanmakuConsumed: (String) -> Unit,
    activeNode: InteractionNode?,
    submitResult: InteractionSubmitResult?,
    submittedNode: InteractionNode?,
    reactionClickCount: Int,
    isSubmitting: Boolean,
    submitError: String?,
    storyContinuationVisible: Boolean,
    storyContinuationState: LoadState<AiStoryContinuationResult>?,
    checkinCardVisible: Boolean,
    checkinCardState: LoadState<AiCheckinCardResult>?,
    onExitFullscreen: () -> Unit,
    onSeekTo: (Long) -> Unit,
    onPlayPause: () -> Unit,
    onReactionClick: (InteractionNode) -> Unit,
    onOptionSelected: (InteractionNode, InteractionOption) -> Unit,
    onSkipNode: (InteractionNode) -> Unit,
    onDismissFeedback: () -> Unit,
    onGenerateStoryContinuation: () -> Unit,
    onPlayStoryContinuation: (AiStoryContinuationResult) -> Unit,
    onDismissStoryContinuation: () -> Unit,
    onGenerateCheckinCard: () -> Unit,
    onDismissCheckinCard: () -> Unit,
    selectedCheckinStyle: String,
    onCheckinStyleSelected: (String) -> Unit,
    safeAreaDebugVisible: Boolean,
) {
    Dialog(
        onDismissRequest = onExitFullscreen,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            ShortPlayVideoSurface(
                exoPlayer = exoPlayer,
                playbackState = playbackState,
                modifier = Modifier.fillMaxSize(),
            )
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clickable(onClick = onPlayPause)
            )
            IconButton(
                onClick = onExitFullscreen,
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(8.dp)
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "退出全屏",
                    tint = Color.White,
                )
            }
            if (!isPlaying && playbackState == Player.STATE_READY &&
                activeNode == null && submitResult == null
            ) {
                Surface(
                    modifier = Modifier.align(Alignment.Center),
                    shape = CircleShape,
                    color = Color.Black.copy(alpha = 0.34f),
                ) {
                    Icon(
                        imageVector = Icons.Default.PlayArrow,
                        contentDescription = "播放",
                        modifier = Modifier.padding(16.dp).size(36.dp),
                        tint = Color.White,
                    )
                }
            }
            if (progressVisible) {
                Surface(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth(),
                    color = Color.Black.copy(alpha = 0.38f),
                ) {
                    CompactPlaybackProgress(
                        positionMs = positionMs,
                        durationMs = durationMs,
                        onSeekTo = onSeekTo,
                    )
                }
            }
            PlayerDanmakuStreamOverlay(
                entries = danmakuEntries,
                enabled = danmakuFlowEnabled,
                modifier = Modifier.fillMaxSize(),
                onConsumed = onDanmakuConsumed,
            )
            if (safeAreaDebugVisible) {
                PlayerSafeAreaDebugLayer(
                    progressVisible = progressVisible,
                    danmakuVisible = danmakuFlowEnabled,
                    activeNode = activeNode,
                    modifier = Modifier.fillMaxSize(),
                )
            }
            activeNode?.let { node ->
                InteractionOverlay(
                    modifier = Modifier
                        .align(interactionOverlayAlignment(node))
                        .interactionSafePadding(
                            node = node,
                            progressVisible = progressVisible,
                            danmakuVisible = danmakuFlowEnabled,
                        ),
                    node = node,
                    isSubmitting = isSubmitting,
                    submitError = submitError,
                    reactionClickCount = reactionClickCount,
                    onReactionClick = { onReactionClick(node) },
                    onOptionSelected = { option -> onOptionSelected(node, option) },
                    onSkip = { onSkipNode(node) },
                )
            }
            submitResult?.let { result ->
                FeedbackOverlay(
                    modifier = Modifier.align(feedbackOverlayAlignment(submittedNode)),
                    result = result,
                    node = submittedNode,
                    onDismiss = onDismissFeedback,
                )
            }
            if (storyContinuationVisible) {
                StoryContinuationOverlay(
                    modifier = Modifier.align(Alignment.Center),
                    state = storyContinuationState,
                    userIntent = "",
                    onUserIntentChange = {},
                    onGenerate = onGenerateStoryContinuation,
                    onPlay = onPlayStoryContinuation,
                    onGenerateCheckin = onGenerateCheckinCard,
                    onDismiss = onDismissStoryContinuation,
                )
            }
            if (checkinCardVisible) {
                CheckinCardOverlay(
                    modifier = Modifier.align(Alignment.Center),
                    state = checkinCardState,
                    selectedStyle = selectedCheckinStyle,
                    userIntent = "",
                    onUserIntentChange = {},
                    onStyleSelected = onCheckinStyleSelected,
                    onGenerate = onGenerateCheckinCard,
                    onDismiss = onDismissCheckinCard,
                )
            }
        }
    }
}

private fun interactionOverlayAlignment(node: InteractionNode): Alignment {
    when (node.placement) {
        "TOP_CENTER" -> return Alignment.TopStart
        "CENTER_END" -> return Alignment.CenterStart
        "CENTER_START" -> return Alignment.CenterStart
        "CENTER" -> return Alignment.CenterStart
        "BOTTOM_CENTER" -> return Alignment.BottomStart
    }
    return Alignment.CenterStart
}

private fun Modifier.interactionSafePadding(
    node: InteractionNode,
    progressVisible: Boolean,
    danmakuVisible: Boolean,
): Modifier {
    val safeArea = node.safeArea
    val top = maxOf(safeArea.topDp, if (safeArea.avoidDanmaku && danmakuVisible) 108 else 0)
    val bottom = maxOf(safeArea.bottomDp, if (safeArea.avoidProgressBar && progressVisible) 96 else 0)
    val end = maxOf(safeArea.endDp, if (safeArea.avoidRightRail) 84 else 0)
    val start = maxOf(safeArea.startDp, 12)
    return this.padding(
        start = start.dp,
        top = top.dp,
        end = end.dp,
        bottom = bottom.dp,
    )
}

private fun feedbackOverlayAlignment(node: InteractionNode?): Alignment {
    return when (node?.visualStyle) {
        "爽点气泡", "笑出鹅叫", "弹幕冲浪" -> Alignment.CenterEnd
        "加速包" -> Alignment.Center
        "身份放大镜", "复盘卡" -> Alignment.CenterStart
        else -> Alignment.BottomCenter
    }
}

@Composable
private fun PlayerSafeAreaDebugLayer(
    progressVisible: Boolean,
    danmakuVisible: Boolean,
    activeNode: InteractionNode?,
    modifier: Modifier = Modifier,
) {
    Box(modifier = modifier) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .border(1.dp, Color(0x88FFB300))
        )
        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(top = 8.dp)
                .background(Color(0xAA000000), RoundedCornerShape(999.dp))
        ) {
            Text(
                text = "顶部标题安全区",
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                color = Color.White,
                style = MaterialTheme.typography.labelSmall,
            )
        }
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 72.dp, end = 8.dp)
                .size(width = 84.dp, height = 260.dp)
                .border(1.dp, Color(0x55FF5252), RoundedCornerShape(16.dp))
                .background(Color(0x22FF5252), RoundedCornerShape(16.dp))
        ) {
            Text(
                text = "右侧操作栏\n避让",
                modifier = Modifier.align(Alignment.Center),
                color = Color.White,
                style = MaterialTheme.typography.labelSmall,
            )
        }
        if (progressVisible) {
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .height(72.dp)
                    .border(1.dp, Color(0x55FFB300), RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp))
                    .background(Color(0x22FFB300), RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp))
            ) {
                Text(
                    text = "进度条安全区",
                    modifier = Modifier.align(Alignment.Center),
                    color = Color.White,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
        if (danmakuVisible) {
            Box(
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .padding(start = 12.dp, end = 92.dp, top = 72.dp)
                    .fillMaxWidth()
                    .height(110.dp)
                    .border(1.dp, Color(0x5539D98A), RoundedCornerShape(18.dp))
                    .background(Color(0x2239D98A), RoundedCornerShape(18.dp))
            ) {
                Text(
                    text = "弹幕安全区",
                    modifier = Modifier.align(Alignment.Center),
                    color = Color.White,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
        activeNode?.let { node ->
            Box(
                modifier = Modifier
                    .align(interactionOverlayAlignment(node))
                    .padding(4.dp)
                    .background(Color(0xAA1E1E1E), RoundedCornerShape(12.dp))
                    .border(1.dp, Color(0x88FFFFFF), RoundedCornerShape(12.dp))
            ) {
                Text(
                    text = "节点安全区：${node.placement} / ${node.componentType}",
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    color = Color.White,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
    }
}

@Composable
private fun PlayerActionIcon(
    icon: ImageVector,
    description: String,
    tint: Color,
    countLabel: String = "",
    onClick: () -> Unit,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Surface(
            shape = CircleShape,
            color = Color.Black.copy(alpha = 0.26f),
            tonalElevation = 2.dp,
        ) {
            IconButton(
                onClick = onClick,
                modifier = Modifier.size(50.dp)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = description,
                    tint = tint,
                )
            }
        }
        if (countLabel.isNotBlank()) {
            Text(
                text = countLabel,
                color = Color.White,
                style = MaterialTheme.typography.labelSmall.copy(
                    shadow = Shadow(
                        color = Color.Black.copy(alpha = 0.72f),
                        offset = Offset(0f, 1.5f),
                        blurRadius = 4f,
                    )
                ),
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun PlayerDanmakuFloatingButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = CircleShape,
        color = Color.Black.copy(alpha = 0.28f),
        tonalElevation = 2.dp,
    ) {
        Text(
            text = "弹",
            modifier = Modifier
                .clickable(onClick = onClick)
                .padding(horizontal = 15.dp, vertical = 12.dp),
            color = Color.White,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun PlayerQuickSpeedEdgeLayer(
    enabled: Boolean,
    onQuickSpeedStart: () -> Unit,
    onQuickSpeedEnd: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (!enabled) {
        return
    }
    Box(modifier = modifier) {
        listOf(Alignment.CenterStart, Alignment.CenterEnd).forEach { alignment ->
            Box(
                modifier = Modifier
                    .align(alignment)
                    .fillMaxHeight()
                    .widthIn(min = 72.dp)
                    .pointerInput(Unit) {
                        awaitEachGesture {
                            awaitFirstDown(requireUnconsumed = false)
                            val releasedBeforeLongPress = withTimeoutOrNull(260) {
                                waitForUpOrCancellation()
                            }
                            if (releasedBeforeLongPress == null) {
                                onQuickSpeedStart()
                                waitForUpOrCancellation()
                                onQuickSpeedEnd()
                            }
                        }
                    }
            )
        }
    }
}

@Composable
private fun PlayerEpisodeTextOverlay(
    title: String,
    intro: String,
    expanded: Boolean,
    onToggleExpanded: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val introScrollState = rememberScrollState()
    LaunchedEffect(expanded, intro) {
        if (!expanded) {
            introScrollState.scrollTo(0)
        }
    }
    Column(
        modifier = modifier
            .widthIn(max = 300.dp)
            .clickable(onClick = onToggleExpanded)
            .padding(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Text(
            text = title,
            color = Color.White,
            style = MaterialTheme.typography.titleMedium.copy(
                shadow = Shadow(
                    color = Color.Black.copy(alpha = 0.78f),
                    offset = Offset(0f, 2f),
                    blurRadius = 6f,
                )
            ),
            fontWeight = FontWeight.Bold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = intro,
            modifier = if (expanded) {
                Modifier
                    .heightIn(max = 188.dp)
                    .verticalScroll(introScrollState)
            } else {
                Modifier
            },
            color = Color.White.copy(alpha = 0.88f),
            style = MaterialTheme.typography.bodySmall.copy(
                shadow = Shadow(
                    color = Color.Black.copy(alpha = 0.78f),
                    offset = Offset(0f, 1.5f),
                    blurRadius = 5f,
                )
            ),
            maxLines = if (expanded) Int.MAX_VALUE else 2,
            overflow = if (expanded) TextOverflow.Clip else TextOverflow.Ellipsis,
        )
        Text(
            text = if (expanded) "收起简介 · 上下滑动查看完整简介" else "展开本集简介",
            color = Color.White.copy(alpha = 0.82f),
            style = MaterialTheme.typography.labelSmall.copy(
                shadow = Shadow(
                    color = Color.Black.copy(alpha = 0.72f),
                    offset = Offset(0f, 1f),
                    blurRadius = 4f,
                )
            ),
        )
    }
}

@Composable
private fun PlayerMoreActionSheet(
    visible: Boolean,
    themeMode: AigcThemeMode,
    playbackSpeed: Float,
    progressBarVisible: Boolean,
    autoPlayNextEpisode: Boolean,
    safeAreaDebugVisible: Boolean,
    onDismiss: () -> Unit,
    onToggleTheme: () -> Unit,
    onOpenAiRecap: () -> Unit,
    onOpenPlaybackInfo: () -> Unit,
    onOpenXRay: () -> Unit,
    onToggleProgress: () -> Unit,
    onOpenEngagement: () -> Unit,
    onSaveMoment: () -> Unit,
    onToggleAutoPlayNext: () -> Unit,
    onCopyLink: () -> Unit,
    onCleanPlayback: () -> Unit,
    onSpeedSelected: (Float) -> Unit,
    onToggleSafeAreaDebug: () -> Unit,
) {
    val themeToggleText = if (themeMode.name == AigcThemeMode.DAY.name) {
        "切换至夜间模式"
    } else {
        "切换至日间模式"
    }
    val speedOptions: List<Float> = listOf(0.75f, 1f, 1.25f, 1.5f, 2f)

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(animationSpec = tween(180)),
        exit = fadeOut(animationSpec = tween(160)),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.34f))
                .clickable(onClick = onDismiss),
            contentAlignment = Alignment.BottomCenter,
        ) {
            AnimatedVisibility(
                visible = visible,
                enter = slideInVertically(
                    initialOffsetY = { it },
                    animationSpec = tween(durationMillis = 260),
                ) + fadeIn(animationSpec = tween(180)),
                exit = slideOutVertically(
                    targetOffsetY = { it },
                    animationSpec = tween(durationMillis = 220),
                ) + fadeOut(animationSpec = tween(160)),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .fillMaxHeight(0.52f)
                        .clickable { }
                        .background(
                            color = Color(0xF2222222),
                            shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
                        )
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.CenterHorizontally)
                            .size(width = 56.dp, height = 5.dp)
                            .background(Color.White.copy(alpha = 0.26f), RoundedCornerShape(999.dp))
                    )
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .verticalScroll(rememberScrollState())
                            .padding(bottom = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        PlayerActionGroup {
                            PlayerSheetActionRow(
                                icon = Icons.Default.AutoAwesome,
                                text = themeToggleText,
                                onClick = onToggleTheme,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.AutoAwesome,
                                text = "AI 摘要",
                                onClick = onOpenAiRecap,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.Speed,
                                text = "播放信息",
                                onClick = onOpenPlaybackInfo,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.Timeline,
                                text = "剧情 X-Ray",
                                onClick = onOpenXRay,
                            )
                        }
                        PlayerActionGroup {
                            PlayerSheetActionRow(
                                icon = Icons.Default.Speed,
                                text = if (progressBarVisible) "收起进度条" else "显示进度条",
                                onClick = onToggleProgress,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.AutoAwesome,
                                text = "互动数据",
                                onClick = onOpenEngagement,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.Favorite,
                                text = "收藏当前爽点",
                                onClick = onSaveMoment,
                            )
                        }
                        PlayerActionGroup {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 14.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Speed,
                                    contentDescription = null,
                                    tint = Color.White.copy(alpha = 0.88f),
                                )
                                Text(
                                    text = "倍速",
                                    modifier = Modifier.widthIn(min = 52.dp),
                                    color = Color.White,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                speedOptions.forEach { speed: Float ->
                                    val selected = abs(playbackSpeed - speed) < 0.01f
                                    Text(
                                        text = if (speed == 1f) "1.0" else speed.toString(),
                                        modifier = Modifier
                                            .clickable { onSpeedSelected(speed) }
                                            .padding(horizontal = 4.dp, vertical = 6.dp),
                                        color = if (selected) Color(0xFFFF4F7A) else Color.White.copy(alpha = 0.54f),
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                    )
                                }
                            }
                            PlayerSheetActionRow(
                                icon = Icons.Default.Fullscreen,
                                text = "清屏播放",
                                onClick = onCleanPlayback,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.PlayArrow,
                                text = if (autoPlayNextEpisode) "自动连播下一集：开" else "自动连播下一集：关",
                                onClick = onToggleAutoPlayNext,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.ContentCopy,
                                text = "复制播放链接",
                                onClick = onCopyLink,
                            )
                            PlayerSheetActionRow(
                                icon = Icons.Default.Timeline,
                                text = if (safeAreaDebugVisible) "安全区调试：关" else "安全区调试：开",
                                onClick = onToggleSafeAreaDebug,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerActionGroup(content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White.copy(alpha = 0.08f), RoundedCornerShape(18.dp)),
        verticalArrangement = Arrangement.spacedBy(0.dp),
        content = content,
    )
}

@Composable
private fun PlayerSheetActionRow(
    icon: ImageVector,
    text: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White.copy(alpha = 0.88f),
        )
        Text(
            text = text,
            color = Color.White,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun PlayerCommentsDialog(
    comments: List<String>,
    draft: String,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 560.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "评论",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                comments.take(8).forEach { comment ->
                    Surface(
                        modifier = Modifier.clickable { onDraftChange(comment) },
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f)
                    ) {
                        Text(
                            text = comment,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                OutlinedTextField(
                    value = draft,
                    onValueChange = onDraftChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(text = "写一条评论") },
                    minLines = 2,
                    maxLines = 4,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(
                        onClick = onSend,
                        enabled = draft.isNotBlank(),
                    ) {
                        Text(text = "发送")
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerDanmakuDialog(
    draft: String,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onDismiss: () -> Unit,
) {
    val presets = listOf("好帅", "这段绝了", "前方高能", "太燃了", "直接起飞", "弹幕护体")
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 560.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "发送弹幕",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                Text(
                    text = "点一下常用词，或者自己写一条直接发到屏幕上。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                presets.chunked(3).forEach { rowPresets ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        rowPresets.forEach { preset ->
                            Surface(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable { onDraftChange(preset) },
                                shape = RoundedCornerShape(999.dp),
                                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f),
                            ) {
                                Text(
                                    text = preset,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                    style = MaterialTheme.typography.labelMedium,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        if (rowPresets.size == 1) {
                            Spacer(modifier = Modifier.weight(1f))
                            Spacer(modifier = Modifier.weight(1f))
                        } else if (rowPresets.size == 2) {
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
                OutlinedTextField(
                    value = draft,
                    onValueChange = onDraftChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(text = "弹幕内容") },
                    minLines = 2,
                    maxLines = 3,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(
                        onClick = onSend,
                        enabled = draft.isNotBlank(),
                    ) {
                        Text(text = "发送")
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerCommentsSheet(
    comments: List<String>,
    draft: String,
    revision: Int,
    onDraftChange: (String) -> Unit,
    onCommentLike: (Int) -> Unit,
    onCommentDislike: (Int) -> Unit,
    onReply: (String) -> Unit,
    onSend: () -> Unit,
    onDismiss: () -> Unit,
) {
    val commentModels = remember(comments, revision) {
        comments.mapIndexed { index, comment ->
            PlayerComment(
                author = listOf("短剧观察员", "反转党", "追更用户", "剧情显微镜")[index % 4],
                content = comment,
                likeCount = 180 + index * 73 + revision,
                replyCount = 6 + index * 3,
                dislikeCount = index % 3,
            )
        }
    }
    PlayerBottomSheet(onDismiss = onDismiss, heightRatio = 0.58f) {
        SheetHandle()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "评论 ${comments.size}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            TextButton(onClick = onDismiss) {
                Text(text = "关闭")
            }
        }
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            commentModels.take(24).forEachIndexed { index, comment ->
                PlayerCommentRow(
                    comment = comment,
                    onLike = { onCommentLike(index) },
                    onDislike = { onCommentDislike(index) },
                    onReply = { onReply(comment.author) },
                )
            }
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = onDraftChange,
                modifier = Modifier.weight(1f),
                label = { Text(text = "写评论") },
                maxLines = 2,
            )
            TextButton(
                onClick = onSend,
                enabled = draft.isNotBlank(),
            ) {
                Text(text = "发送")
            }
        }
    }
}

@Composable
private fun PlayerCommentRow(
    comment: PlayerComment,
    onLike: () -> Unit,
    onDislike: () -> Unit,
    onReply: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Surface(
            modifier = Modifier.size(34.dp),
            shape = CircleShape,
            color = MaterialTheme.colorScheme.primaryContainer,
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = comment.author.take(1),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
        }
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text(
                text = comment.author,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = comment.content,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "赞 ${formatCompactCount(comment.likeCount)}",
                    modifier = Modifier.clickable(onClick = onLike),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "回复 ${comment.replyCount}",
                    modifier = Modifier.clickable(onClick = onReply),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "点踩 ${comment.dislikeCount}",
                    modifier = Modifier.clickable(onClick = onDislike),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun PlayerDanmakuSheet(
    draft: String,
    alpha: Float,
    speedMultiplier: Float,
    fontSizeSp: Float,
    areaRatio: Float,
    onDraftChange: (String) -> Unit,
    onAlphaChange: (Float) -> Unit,
    onSpeedChange: (Float) -> Unit,
    onFontSizeChange: (Float) -> Unit,
    onAreaRatioChange: (Float) -> Unit,
    onSend: () -> Unit,
    onDismiss: () -> Unit,
) {
    val presets = listOf("好帅", "这段绝了", "前方高能", "太燃了", "直接起飞", "弹幕护体")
    PlayerBottomSheet(onDismiss = onDismiss, heightRatio = 0.58f) {
        SheetHandle()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "弹幕",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            TextButton(onClick = onDismiss) {
                Text(text = "关闭")
            }
        }
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            presets.chunked(3).forEach { rowPresets ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    rowPresets.forEach { preset ->
                        Surface(
                            modifier = Modifier
                                .weight(1f)
                                .clickable { onDraftChange(preset) },
                            shape = RoundedCornerShape(999.dp),
                            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f),
                        ) {
                            Text(
                                text = preset,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                style = MaterialTheme.typography.labelMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                    repeat(3 - rowPresets.size) {
                        Spacer(modifier = Modifier.weight(1f))
                    }
                }
            }
            DanmakuSettingSlider("透明度", "${(alpha * 100).roundToInt()}%", alpha, 0.35f..1f, onAlphaChange)
            DanmakuSettingSlider("移动速度", "${String.format(Locale.US, "%.1f", speedMultiplier)}x", speedMultiplier, 0.6f..1.8f, onSpeedChange)
            DanmakuSettingSlider("字体大小", "${fontSizeSp.roundToInt()}sp", fontSizeSp, 12f..22f, onFontSizeChange)
            DanmakuSettingSlider("显示区域", "上方 ${(areaRatio * 100).roundToInt()}%", areaRatio, 0.24f..0.68f, onAreaRatioChange)
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = onDraftChange,
                modifier = Modifier.weight(1f),
                label = { Text(text = "弹幕内容") },
                maxLines = 2,
            )
            TextButton(
                onClick = onSend,
                enabled = draft.isNotBlank(),
            ) {
                Text(text = "发送")
            }
        }
    }
}

@Composable
private fun PlayerBottomSheet(
    onDismiss: () -> Unit,
    heightRatio: Float,
    content: @Composable ColumnScope.() -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.34f))
            .clickable(onClick = onDismiss),
        contentAlignment = Alignment.BottomCenter,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(heightRatio)
                .clickable { }
                .background(
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
                ),
            content = content,
        )
    }
}

@Composable
private fun SheetHandle() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp, bottom = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .size(width = 54.dp, height = 5.dp)
                .background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.16f), RoundedCornerShape(999.dp))
        )
    }
}

@Composable
private fun DanmakuSettingSlider(
    title: String,
    valueText: String,
    value: Float,
    valueRange: ClosedFloatingPointRange<Float>,
    onValueChange: (Float) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = title, style = MaterialTheme.typography.bodyMedium)
            Text(
                text = valueText,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = valueRange,
        )
    }
}

@Composable
private fun PlayerDanmakuStreamOverlay(
    entries: List<PlayerDanmakuEntry>,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    alpha: Float = 0.86f,
    speedMultiplier: Float = 1f,
    fontSizeSp: Float = 15f,
    areaRatio: Float = 0.42f,
    onConsumed: (String) -> Unit,
) {
    if (!enabled) {
        return
    }
    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val density = LocalDensity.current
        val maxWidthPx = with(density) { maxWidth.toPx() }
        val maxHeightPx = with(density) { maxHeight.toPx() }
        if (maxWidthPx <= 0f || maxHeightPx <= 0f) {
            return@BoxWithConstraints
        }
        val edgePaddingPx = with(density) { 32.dp.toPx() }
        val startX = maxWidthPx + edgePaddingPx
        val laneHeightPx = with(density) { (fontSizeSp + 18).dp.toPx() }
        val visibleHeightPx = maxHeightPx * areaRatio.coerceIn(0.24f, 0.68f)
        val laneCount = min(
            PLAYER_DANMAKU_LANE_COUNT,
            (visibleHeightPx / laneHeightPx).roundToInt().coerceAtLeast(1)
        )
        val safeEntries = entries.takeLast(PLAYER_DANMAKU_MAX_ACTIVE)
        safeEntries.forEachIndexed { index, entry ->
            key(entry.entryId) {
                val offsetX = remember(entry.entryId, startX) { Animatable(startX) }
                val laneIndex = entry.lane % laneCount
                val offsetY = with(density) { 56.dp.toPx() } + laneIndex * laneHeightPx
                LaunchedEffect(entry.entryId, startX) {
                    delay(index * 420L)
                    val estimatedTextWidthPx = with(density) {
                        (entry.text.length.coerceIn(4, 18) * fontSizeSp * 0.72f).dp.toPx()
                    }
                    val endX = -(estimatedTextWidthPx + edgePaddingPx + with(density) { 4.dp.toPx() })
                    offsetX.snapTo(startX)
                    offsetX.animateTo(
                        targetValue = endX,
                        animationSpec = tween(
                            durationMillis = ((if (entry.isUserGenerated) 8200 else 9800) / speedMultiplier.coerceIn(0.6f, 1.8f)).roundToInt(),
                            easing = LinearEasing,
                        )
                    )
                    onConsumed(entry.entryId)
                }
                Text(
                    text = entry.text,
                    modifier = Modifier.offset {
                        IntOffset(offsetX.value.roundToInt(), offsetY.roundToInt())
                    }
                        .widthIn(max = 320.dp)
                        .alpha(alpha.coerceIn(0.35f, 1f)),
                    color = if (entry.isUserGenerated) Color(0xFFFFE56B) else Color.White,
                    style = MaterialTheme.typography.labelMedium.copy(
                        fontSize = fontSizeSp.coerceIn(12f, 22f).sp,
                        shadow = Shadow(
                            color = Color.Black.copy(alpha = 0.82f),
                            offset = Offset(1.2f, 1.8f),
                            blurRadius = 4f,
                        )
                    ),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun PlayerAiRecapDialog(
    episodeTitle: String,
    state: LoadState<AiContentRecapResult>?,
    onGenerate: () -> Unit,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 560.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "AI 摘要",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                Text(
                    text = "当前集：$episodeTitle",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                when (val current = state) {
                    null -> Text(
                        text = "尚未生成摘要",
                        style = MaterialTheme.typography.bodyMedium,
                    )

                    LoadState.Loading -> Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp))
                        Text(text = "正在生成摘要")
                    }

                    is LoadState.Error -> Text(
                        text = current.message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )

                    is LoadState.Success -> {
                        val recap = current.data
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text(
                                text = recap.summary,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            if (recap.highlights.isNotEmpty()) {
                                Text(
                                    text = "高能点",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                recap.highlights.take(5).forEach { item ->
                                    Text(text = "• $item", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                            if (recap.characterFocus.isNotEmpty()) {
                                Text(
                                    text = "角色聚焦",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                Text(
                                    text = recap.characterFocus.joinToString(" / "),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                            if (recap.discussionSeeds.isNotEmpty()) {
                                Text(
                                    text = "讨论延展",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                recap.discussionSeeds.take(4).forEach { item ->
                                    Text(text = "• $item", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                            Text(
                                text = "继续看下去：${recap.continueReason}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(onClick = onGenerate) {
                        Text(text = "重新生成")
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerEngagementDialog(
    insightsState: LoadState<InteractionInsights>,
    historyState: LoadState<List<InteractionLocalRecord>>,
    onSeekTo: (Long) -> Unit,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 640.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "互动数据",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                when (val current = insightsState) {
                    LoadState.Loading -> Text(text = "互动热力图正在加载")
                    is LoadState.Error -> Text(
                        text = current.message,
                        color = MaterialTheme.colorScheme.error,
                    )
                    is LoadState.Success -> InteractionInsightsPanel(
                        insights = current.data,
                        onSeekTo = onSeekTo,
                    )
                }
                when (val current = historyState) {
                    LoadState.Loading -> Text(text = "本地互动记录正在加载")
                    is LoadState.Error -> Text(
                        text = current.message,
                        color = MaterialTheme.colorScheme.error,
                    )
                    is LoadState.Success -> InteractionHistoryPanel(current.data)
                }
            }
        }
    }
}

@Composable
private fun PlayerPlaybackInfoDialog(
    playbackState: Int,
    isPlaying: Boolean,
    playUrl: String,
    currentPlayUrl: String,
    isBranchPlayback: Boolean,
    hlsAvailable: Boolean,
    positionMs: Long,
    durationMs: Long,
    retryCount: Int,
    errorCode: String?,
    errorMessage: String?,
    onRetry: () -> Unit,
    onDismiss: () -> Unit,
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 560.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "播放信息",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                PlaybackDiagnosticsPanel(
                    playbackState = playbackState,
                    isPlaying = isPlaying,
                    playUrl = playUrl,
                    currentPlayUrl = currentPlayUrl,
                    isBranchPlayback = isBranchPlayback,
                    hlsAvailable = hlsAvailable,
                    positionMs = positionMs,
                    durationMs = durationMs,
                    retryCount = retryCount,
                    errorCode = errorCode,
                    errorMessage = errorMessage,
                    onRetry = onRetry,
                )
            }
        }
    }
}

@Composable
private fun PlayerStoryXRayDialog(
    interactionConfig: InteractionConfig,
    positionMs: Long,
    onSeekTo: (Long) -> Unit,
    onDismiss: () -> Unit,
) {
    val sortedNodes = interactionConfig.nodes.sortedBy { abs(it.triggerMs - positionMs) }
    val sortedTimedEvents = interactionConfig.timedEvents.sortedBy {
        abs(((it.startMs + it.endMs) / 2L) - positionMs)
    }
    val evidenceGraph = interactionConfig.evidenceGraph
    val graphNodes = evidenceGraph?.nodes.orEmpty().sortedBy { abs(it.timeMs - positionMs) }
    val currentNode = sortedNodes.firstOrNull()?.takeIf { abs(it.triggerMs - positionMs) <= 20_000L }
    val currentTimedEvent = sortedTimedEvents.firstOrNull()?.takeIf {
        abs(((it.startMs + it.endMs) / 2L) - positionMs) <= 20_000L
    }
    val currentGraphNode = graphNodes.firstOrNull()?.takeIf { abs(it.timeMs - positionMs) <= 20_000L }
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .heightIn(max = 660.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(
                            text = "剧情 X-Ray",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            text = "当前时间点对应的剧情标签、证据和可跳转时间",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = onDismiss) {
                        Text(text = "关闭")
                    }
                }
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    Text(
                        text = "当前位置：${formatPlaybackTime(positionMs)}",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
                if (currentTimedEvent != null) {
                    PlayerStoryXRayTimelineCard(
                        event = currentTimedEvent,
                        isCurrent = true,
                        distanceMs = abs(((currentTimedEvent.startMs + currentTimedEvent.endMs) / 2L) - positionMs),
                        onSeekTo = onSeekTo,
                    )
                } else {
                    Text(text = "当前没有可追踪的标准时间标签")
                }
                if (evidenceGraph != null && currentGraphNode != null) {
                    PlayerStoryXRayEvidenceGraphCard(
                        graph = evidenceGraph,
                        node = currentGraphNode,
                        isCurrent = true,
                        onSeekTo = onSeekTo,
                    )
                }
                if (currentNode == null) {
                    Text(text = "当前没有可追踪的剧情节点")
                } else {
                    PlayerStoryXRayNodeCard(
                        node = currentNode,
                        isCurrent = true,
                        distanceMs = abs(currentNode.triggerMs - positionMs),
                        onSeekTo = onSeekTo,
                    )
                }
                Text(
                    text = "证据图谱",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                if (evidenceGraph == null || evidenceGraph.nodes.isEmpty()) {
                    Text(text = "当前剧集还没有可解析的多模态证据图谱")
                } else {
                    graphNodes.take(4).forEach { graphNode ->
                        PlayerStoryXRayEvidenceGraphCard(
                            graph = evidenceGraph,
                            node = graphNode,
                            isCurrent = currentGraphNode?.nodeId == graphNode.nodeId,
                            onSeekTo = onSeekTo,
                        )
                    }
                }
                Text(
                    text = "时间标签",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                if (sortedTimedEvents.isEmpty()) {
                    Text(text = "当前剧集还没有标准时间标签")
                } else {
                    sortedTimedEvents.take(5).forEach { event ->
                        PlayerStoryXRayTimelineCard(
                            event = event,
                            isCurrent = currentTimedEvent?.eventId == event.eventId,
                            distanceMs = abs(((event.startMs + event.endMs) / 2L) - positionMs),
                            onSeekTo = onSeekTo,
                        )
                    }
                }
                Text(
                    text = "附近节点",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                if (sortedNodes.isEmpty()) {
                    Text(text = "当前剧集还没有时间轴节点")
                } else {
                    sortedNodes.take(5).forEach { node ->
                        PlayerStoryXRayNodeCard(
                            node = node,
                            isCurrent = currentNode?.id == node.id,
                            distanceMs = abs(node.triggerMs - positionMs),
                            onSeekTo = onSeekTo,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerStoryXRayEvidenceGraphCard(
    graph: EvidenceGraph,
    node: EvidenceGraphNode,
    isCurrent: Boolean,
    onSeekTo: (Long) -> Unit,
) {
    val evidenceByRef = graph.evidence.associateBy { it.refId }
    val evidenceItems = node.resolvedEvidenceRefs.mapNotNull { evidenceByRef[it] }
    val explanation = graph.explanations.firstOrNull { it.nodeId == node.nodeId }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onSeekTo(node.timeMs) },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "证据链 · ${node.componentType.ifBlank { "INTERACTION" }}",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = formatPlaybackTime(node.timeMs),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                text = explanation?.explainText?.ifBlank { null }
                    ?: node.whyText.ifBlank { "${node.title} 已绑定 ${node.evidenceRefs.size} 条证据。" },
                style = MaterialTheme.typography.bodySmall,
            )
            if (explanation != null) {
                Text(
                    text = "语义标签：${explanation.storyTags.takeIf { it.isNotEmpty() }?.joinToString(" / ") ?: "待补充"} · 共鸣：${explanation.audienceResonance.ifBlank { "观众共鸣" }}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "证据摘要：${explanation.evidenceSummary.ifBlank { "人工审核节点" }}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            val facets = graph.storyFacets
            val facetText = listOf(
                facets.characters.takeIf { it.isNotEmpty() }?.joinToString(" / ")?.let { "人物 $it" },
                facets.conflicts.takeIf { it.isNotEmpty() }?.joinToString(" / ")?.let { "冲突 $it" },
                facets.reversals.takeIf { it.isNotEmpty() }?.joinToString(" / ")?.let { "反转 $it" },
            ).filterNotNull().joinToString(" · ")
            if (facetText.isNotBlank()) {
                Text(
                    text = facetText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                text = "来源：${node.generationSource.ifBlank { "manual" }} · 置信度：${formatConfidenceScore(node.confidence)} · 复核：${node.reviewStatus.ifBlank { "unknown" }}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (evidenceItems.isEmpty()) {
                Text(
                    text = "证据引用：${node.evidenceRefs.takeIf { it.isNotEmpty() }?.joinToString(" / ") ?: "无"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                evidenceItems.take(4).forEach { evidence ->
                    Text(
                        text = "• ${evidence.sourceLabel} ${formatPlaybackTime(evidence.timeMs)}：${evidence.displayText.ifBlank { evidence.refId }}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            TextButton(onClick = { onSeekTo(node.timeMs) }) {
                Text(text = "跳到证据时间点")
            }
        }
    }
}

@Composable
private fun PlayerStoryXRayNodeCard(
    node: InteractionNode,
    isCurrent: Boolean,
    distanceMs: Long,
    onSeekTo: (Long) -> Unit,
) {
    val profile = node.componentProfile()
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onSeekTo(node.triggerMs) },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = if (isCurrent) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.secondaryContainer,
                ) {
                    Text(
                        text = profile.displayName,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
                Text(
                    text = "跳转 ${formatPlaybackTime(node.triggerMs)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                text = node.title.ifBlank { node.promptText.ifBlank { "未命名剧情节点" } },
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            if (node.subtitle.isNotBlank()) {
                Text(
                    text = node.subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = "标签：${profile.displayName} · 来源：${node.generationSource.ifBlank { "manual" }} · 置信度：${formatConfidenceScore(node.confidence)} · 复核：${node.reviewStatus.ifBlank { "unknown" }}",
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                text = "语义：${profile.summary}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "安全区：${profile.safeAreaHint}；默认位点：${profile.defaultPlacement}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "证据：${node.evidenceRefs.takeIf { it.isNotEmpty() }?.joinToString(" / ") ?: "无"}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (distanceMs > 0L) {
                Text(
                    text = "距离当前 ${formatPlaybackTime(distanceMs)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = { onSeekTo(node.triggerMs) }) {
                Text(text = "跳到这个时间点")
            }
        }
    }
}

@Composable
private fun PlayerStoryXRayTimelineCard(
    event: InteractionTimedEvent,
    isCurrent: Boolean,
    distanceMs: Long,
    onSeekTo: (Long) -> Unit,
) {
    val profile = event.componentProfile()
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onSeekTo(event.startMs) },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = if (isCurrent) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.secondaryContainer,
                ) {
                    Text(
                        text = profile.displayName,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
                Text(
                    text = "窗口 ${formatPlaybackTime(event.startMs)} - ${formatPlaybackTime(event.endMs)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                text = "组件：${profile.displayName}（${event.componentType}）; 样式：${event.visualStyle.ifBlank { "默认" }}; 位置：${event.placement}; 来源：${event.generationSource.ifBlank { "manual" }}; 复核：${event.reviewStatus.ifBlank { "unknown" }}; 置信度：${formatConfidenceScore(event.confidence)}",
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                text = "语义：${profile.summary}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "证据：${event.evidenceRefs.takeIf { it.isNotEmpty() }?.joinToString(" / ") ?: "无"}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "safeArea：T${event.safeArea.topDp}/B${event.safeArea.bottomDp}/S${event.safeArea.startDp}/E${event.safeArea.endDp} · maxLines：${event.maxLines} · analyticsKey：${event.analyticsKey} · hash：${event.payloadHash.takeIf { it.isNotBlank() } ?: "unknown"}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (distanceMs > 0L) {
                Text(
                    text = "距离当前 ${formatPlaybackTime(distanceMs)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = { onSeekTo(event.startMs) }) {
                Text(text = "跳到这个时间窗口")
            }
        }
    }
}

@Composable
private fun PlaybackDiagnosticsPanel(
    playbackState: Int,
    isPlaying: Boolean,
    playUrl: String,
    currentPlayUrl: String,
    isBranchPlayback: Boolean,
    hlsAvailable: Boolean,
    positionMs: Long,
    durationMs: Long,
    retryCount: Int,
    errorCode: String?,
    errorMessage: String?,
    onRetry: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "播放状态",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                TextButton(onClick = onRetry) {
                    Text(text = "重试")
                }
            }
            Text(
                text = "${playbackStateLabel(playbackState)} / ${if (isPlaying) "正在播放" else "未播放"} / ${when {
                    isBranchPlayback -> "AIGC插片"
                    hlsAvailable && currentPlayUrl != playUrl -> "HLS"
                    else -> "MP4"
                }}",
                style = MaterialTheme.typography.bodySmall,
                color = if (errorMessage == null) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            )
            Text(
                text = "进度 ${formatPlaybackTime(positionMs)} / ${formatPlaybackTime(durationMs)}；重试 $retryCount 次",
                style = MaterialTheme.typography.bodySmall,
            )
            if (errorCode != null || errorMessage != null) {
                Text(
                    text = "错误码：${errorCode ?: "UNKNOWN"}；${errorMessage ?: "无错误详情"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            Text(
                text = "当前：$currentPlayUrl",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (currentPlayUrl != playUrl) {
                Text(
                    text = "回退地址：$playUrl",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun CompactPlaybackProgress(
    positionMs: Long,
    durationMs: Long,
    onSeekTo: (Long) -> Unit,
) {
    val safeDurationMs = durationMs.coerceAtLeast(0L)
    val safePositionMs = if (safeDurationMs > 0L) {
        positionMs.coerceIn(0L, safeDurationMs)
    } else {
        0L
    }
    var draggingPositionMs by remember(safeDurationMs) { mutableStateOf<Long?>(null) }
    val displayPositionMs = (draggingPositionMs ?: safePositionMs).coerceIn(0L, safeDurationMs)

    Slider(
        value = displayPositionMs.toFloat(),
        onValueChange = { value ->
            draggingPositionMs = value.toLong().coerceIn(0L, safeDurationMs)
        },
        onValueChangeFinished = {
            draggingPositionMs?.let(onSeekTo)
            draggingPositionMs = null
        },
        valueRange = 0f..safeDurationMs.toFloat().coerceAtLeast(1f),
        enabled = safeDurationMs > 0L,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 18.dp, vertical = 2.dp)
            .height(10.dp),
    )
}

private fun Modifier.playerTapAndSwipeGesture(
    onTap: () -> Unit,
    onSwipeUp: () -> Unit,
): Modifier {
    return pointerInput(onTap, onSwipeUp) {
        awaitEachGesture {
            val down = awaitFirstDown(requireUnconsumed = false)
            var pointerId = down.id
            var lastPosition = down.position
            var totalDrag = Offset.Zero
            var isSwipe = false
            while (true) {
                val event = awaitPointerEvent(PointerEventPass.Main)
                val change = event.changes.firstOrNull { it.id == pointerId } ?: event.changes.firstOrNull()
                if (change == null) {
                    break
                }
                pointerId = change.id
                val delta = change.position - lastPosition
                lastPosition = change.position
                totalDrag += delta
                if (abs(totalDrag.y) > 72f && abs(totalDrag.y) > abs(totalDrag.x) * 1.35f) {
                    isSwipe = true
                    change.consume()
                }
                if (!change.pressed) {
                    break
                }
            }
            if (isSwipe && totalDrag.y < -72f) {
                onSwipeUp()
            } else if (!isSwipe && abs(totalDrag.x) < 18f && abs(totalDrag.y) < 18f) {
                onTap()
            }
        }
    }
}

@Composable
private fun PlayerEpisodePickerBar(
    playbackEpisode: PlaybackEpisode,
    episodes: List<EpisodeCard>,
    progressMs: Long,
    durationMs: Long,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val currentEpisode = episodes.firstOrNull { it.episodeId == playbackEpisode.episodeId }
    val currentNo = currentEpisode?.episodeNo ?: episodeNoFromEpisodeId(playbackEpisode.episodeId)
    val totalCount = episodes.size.takeIf { it > 0 } ?: currentNo.coerceAtLeast(1)
    val progressFraction = if (durationMs > 0L) {
        (progressMs.toFloat() / durationMs.toFloat()).coerceIn(0f, 1f)
    } else {
        0f
    }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .pressScaleClickable(onClick = onClick),
        shape = RoundedCornerShape(18.dp),
        color = Color.Black.copy(alpha = 0.44f),
        tonalElevation = 4.dp,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "选集 · 第${currentNo}集 · 共${totalCount}集",
                    color = Color.White,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "⌃",
                    color = Color.White.copy(alpha = 0.88f),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .background(Color.White.copy(alpha = 0.12f), RoundedCornerShape(999.dp)),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(progressFraction)
                        .height(3.dp)
                        .background(Color(0xFFFF6A2A), RoundedCornerShape(999.dp)),
                )
            }
        }
    }
}

@Composable
private fun PlayerEpisodePickerSheet(
    episodes: List<EpisodeCard>,
    currentEpisodeId: String,
    onEpisodeClick: (EpisodeCard) -> Unit,
    onDismiss: () -> Unit,
) {
    AnimatedVisibility(
        visible = true,
        enter = fadeIn(animationSpec = tween(180)),
        exit = fadeOut(animationSpec = tween(160)),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.42f))
                .clickable(onClick = onDismiss),
            contentAlignment = Alignment.BottomCenter,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.48f)
                    .clickable { }
                    .background(
                        color = Color(0xF21A1A1A),
                        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
                    )
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Box(
                    modifier = Modifier
                        .align(Alignment.CenterHorizontally)
                        .size(width = 52.dp, height = 5.dp)
                        .background(Color.White.copy(alpha = 0.24f), RoundedCornerShape(999.dp))
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "选集",
                        color = Color.White,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = "共${episodes.size}集",
                        color = Color.White.copy(alpha = 0.62f),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                LazyVerticalGrid(
                    columns = GridCells.Fixed(5),
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(bottom = 18.dp),
                ) {
                    gridItems(episodes.sortedBy { it.episodeNo }, key = { it.episodeId }) { episode ->
                        val selected = episode.episodeId == currentEpisodeId
                        Surface(
                            modifier = Modifier
                                .height(42.dp)
                                .pressScaleClickable { onEpisodeClick(episode) },
                            shape = RoundedCornerShape(12.dp),
                            color = if (selected) Color(0xFFFF6A2A) else Color.White.copy(alpha = 0.10f),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Text(
                                    text = episode.episodeNo.toString(),
                                    color = Color.White,
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun InteractionOverlay(
    modifier: Modifier = Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    reactionClickCount: Int,
    onReactionClick: () -> Unit,
    onOptionSelected: (InteractionOption) -> Unit,
    onSkip: () -> Unit,
) {
    val profile = node.componentProfile()
    AnimatedInteractionChrome(
        nodeId = node.id,
        modifier = modifier,
    ) {
        when (profile.componentType) {
            "REACTION_STICKER" -> ReactionBubbleOverlay(
                modifier = Modifier,
                node = node,
                isSubmitting = isSubmitting,
                submitError = submitError,
                clickCount = reactionClickCount,
                onReactionClick = onReactionClick,
                onSkip = onSkip,
            )

            "DANMAKU_STICKER" -> DanmakuOverlay(
                modifier = Modifier,
                node = node,
                isSubmitting = isSubmitting,
                submitError = submitError,
                onOptionSelected = onOptionSelected,
                onSkip = onSkip,
            )

            "AIGC_CARD" -> AccelerationOverlay(
                modifier = Modifier,
                node = node,
                isSubmitting = isSubmitting,
                submitError = submitError,
                onOptionSelected = onOptionSelected,
                onSkip = onSkip,
            )

            "EVIDENCE_CARD" -> InfoLensOverlay(
                modifier = Modifier,
                node = node,
                isSubmitting = isSubmitting,
                submitError = submitError,
                onOptionSelected = onOptionSelected,
                onSkip = onSkip,
            )

            else -> ChoiceRibbonOverlay(
                modifier = Modifier,
                node = node,
                isSubmitting = isSubmitting,
                submitError = submitError,
                onOptionSelected = onOptionSelected,
                onSkip = onSkip,
            )
        }
    }
}

@Composable
private fun AnimatedInteractionChrome(
    nodeId: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    var entered by remember(nodeId) { mutableStateOf(false) }
    LaunchedEffect(nodeId) {
        entered = true
    }
    val alpha by animateFloatAsState(
        targetValue = if (entered) 1f else 0f,
        animationSpec = tween(durationMillis = 220, easing = FastOutSlowInEasing),
        label = "interaction_overlay_alpha",
    )
    val scale by animateFloatAsState(
        targetValue = if (entered) 1f else 0.92f,
        animationSpec = tween(durationMillis = 260, easing = FastOutSlowInEasing),
        label = "interaction_overlay_scale",
    )
    Box(
        modifier = modifier.graphicsLayer {
            this.alpha = alpha
            scaleX = scale
            scaleY = scale
            translationY = (1f - alpha) * 28f
        }
    ) {
        content()
    }
}

@Composable
private fun Modifier.pressScaleClickable(
    enabled: Boolean = true,
    onClick: () -> Unit,
): Modifier {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (enabled && pressed) 0.96f else 1f,
        animationSpec = tween(durationMillis = 110, easing = FastOutSlowInEasing),
        label = "interaction_press_scale",
    )
    return graphicsLayer {
        scaleX = scale
        scaleY = scale
    }.clickable(
        interactionSource = interactionSource,
        indication = null,
        enabled = enabled,
        onClick = onClick,
    )
}

@Composable
private fun AnimatedInteractionButton(
    onClick: () -> Unit,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (enabled && pressed) 0.96f else 1f,
        animationSpec = tween(durationMillis = 110, easing = FastOutSlowInEasing),
        label = "interaction_button_scale",
    )
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.graphicsLayer {
            scaleX = scale
            scaleY = scale
        },
        shape = RoundedCornerShape(20.dp),
        interactionSource = interactionSource,
    ) {
        content()
    }
}

@Composable
private fun ReactionBubbleOverlay(
    modifier: Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    clickCount: Int,
    onReactionClick: () -> Unit,
    onSkip: () -> Unit,
) {
    Surface(
        modifier = modifier
            .widthIn(max = 170.dp)
            .padding(end = 12.dp),
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.90f),
        tonalElevation = 8.dp,
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Surface(
                modifier = Modifier
                    .size(86.dp)
                    .pressScaleClickable(
                        enabled = !isSubmitting,
                        onClick = onReactionClick,
                    ),
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primary,
                tonalElevation = 10.dp,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        text = node.effectText.ifBlank { "爽" },
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.onPrimary,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
            Text(
                text = "×${clickCount.coerceAtLeast(0)}",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            if (submitError != null) {
                Text(
                    text = submitError,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            if (node.allowSkip) {
                TextButton(onClick = onSkip, enabled = !isSubmitting) {
                    Text(text = "收起")
                }
            }
        }
    }
}

@Composable
private fun DanmakuOverlay(
    modifier: Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    onOptionSelected: (InteractionOption) -> Unit,
    onSkip: () -> Unit,
) {
    Surface(
        modifier = modifier
            .widthIn(max = 330.dp)
            .padding(8.dp),
        shape = RoundedCornerShape(999.dp),
        color = Color.Black.copy(alpha = 0.54f),
    ) {
        Row(
            modifier = Modifier
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 10.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = node.effectText.ifBlank { "弹" },
                color = Color.White,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            node.options.forEach { option ->
                Surface(
                    modifier = Modifier.pressScaleClickable(
                        enabled = !isSubmitting,
                        onClick = { onOptionSelected(option) },
                    ),
                    shape = RoundedCornerShape(18.dp),
                    color = MaterialTheme.colorScheme.secondaryContainer,
                ) {
                    Text(
                        text = option.text,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = node.maxLines,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            if (node.allowSkip) {
                TextButton(onClick = onSkip, enabled = !isSubmitting) {
                    Text(text = "关闭")
                }
            }
        }
    }
    InteractionStatusLine(isSubmitting, submitError)
}

@Composable
private fun AccelerationOverlay(
    modifier: Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    onOptionSelected: (InteractionOption) -> Unit,
    onSkip: () -> Unit,
) {
    BoxWithConstraints(modifier = modifier) {
        val scrollState = rememberScrollState()
        Card(
            modifier = Modifier
                .widthIn(max = 330.dp)
                .heightIn(max = (maxHeight - 24.dp).coerceAtLeast(240.dp))
                .padding(12.dp)
                .border(1.dp, MaterialTheme.colorScheme.tertiary, RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(scrollState)
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(text = "AI 生成剧情推进卡", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                if (node.aiInsertMediaUrl.isNotBlank()) {
                    AigcInsertClipPreview(
                        mediaUrl = node.aiInsertMediaUrl,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("冲突提速", "爽点预热", "继续播放").forEach { label ->
                        Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface.copy(alpha = 0.7f)) {
                            Text(
                                text = label,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }
                }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(12.dp)
                        .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.55f), RoundedCornerShape(20.dp))
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth(0.72f)
                            .height(12.dp)
                            .background(MaterialTheme.colorScheme.tertiary, RoundedCornerShape(20.dp))
                    )
                }
                Text(
                    text = node.aiInsertTitle.ifBlank { node.title },
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = node.maxLines,
                    overflow = TextOverflow.Ellipsis,
                )
                if (node.aiInsertHighEnergyLine.isNotBlank()) {
                    Text(
                        text = "高能台词：${node.aiInsertHighEnergyLine}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
                if (node.aiInsertDescription.isNotBlank()) {
                    Text(text = node.aiInsertDescription, style = MaterialTheme.typography.bodySmall)
                }
                if (node.aiInsertProviderName.isNotBlank()) {
                    Text(
                        text = "Provider：${node.aiInsertProviderName}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    node.options.chunked(2).forEach { rowOptions ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            rowOptions.forEach { option ->
                                AnimatedInteractionButton(
                                    onClick = { onOptionSelected(option) },
                                    enabled = !isSubmitting,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text(text = option.text, maxLines = 1)
                                }
                            }
                            if (rowOptions.size == 1) {
                                Spacer(modifier = Modifier.weight(1f))
                            }
                        }
                    }
                }
                if (node.allowSkip) {
                    TextButton(onClick = onSkip, enabled = !isSubmitting) {
                        Text(text = node.skipText.ifBlank { "跳过" })
                    }
                }
                InteractionStatusLine(isSubmitting, submitError)
            }
        }
    }
}

@Composable
private fun InfoLensOverlay(
    modifier: Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    onOptionSelected: (InteractionOption) -> Unit,
    onSkip: () -> Unit,
) {
    Card(
        modifier = modifier
            .widthIn(max = 280.dp)
            .padding(start = 12.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.94f))
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(text = node.badgeText.ifBlank { node.visualStyle }, style = MaterialTheme.typography.labelLarge)
            Text(
                text = node.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = node.maxLines,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = node.subtitle,
                style = MaterialTheme.typography.bodySmall,
                maxLines = node.maxLines,
                overflow = TextOverflow.Ellipsis,
            )
            node.options.forEach { option ->
                TextButton(onClick = { onOptionSelected(option) }, enabled = !isSubmitting) {
                    Text(text = option.text)
                }
            }
            if (node.allowSkip) {
                TextButton(onClick = onSkip, enabled = !isSubmitting) {
                    Text(text = node.skipText.ifBlank { "收起" })
                }
            }
            InteractionStatusLine(isSubmitting, submitError)
        }
    }
}

@Composable
private fun ChoiceRibbonOverlay(
    modifier: Modifier,
    node: InteractionNode,
    isSubmitting: Boolean,
    submitError: String?,
    onOptionSelected: (InteractionOption) -> Unit,
    onSkip: () -> Unit,
) {
    Surface(
        modifier = modifier
            .widthIn(max = 330.dp)
            .padding(8.dp),
        shape = RoundedCornerShape(22.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.88f),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = node.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = node.maxLines,
                overflow = TextOverflow.Ellipsis,
            )
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                node.options.forEach { option ->
                    AnimatedInteractionButton(
                        onClick = { onOptionSelected(option) },
                        enabled = !isSubmitting,
                    ) {
                        Text(text = option.text, maxLines = node.maxLines, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                InteractionStatusLine(isSubmitting, submitError)
                Spacer(modifier = Modifier.weight(1f))
                if (node.allowSkip) {
                    TextButton(onClick = onSkip, enabled = !isSubmitting) {
                        Text(text = node.skipText.ifBlank { "跳过" })
                    }
                }
            }

        }
    }
}

@Composable
private fun InteractionStatusLine(isSubmitting: Boolean, submitError: String?) {
    if (isSubmitting) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator(modifier = Modifier.size(16.dp))
            Text(text = "正在生成互动反馈", style = MaterialTheme.typography.bodySmall)
        }
    }
    if (submitError != null) {
        Text(
            text = submitError,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error
        )
    }
}

@Composable
private fun InteractionInsightsPanel(
    insights: InteractionInsights,
    onSeekTo: (Long) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = "互动热力图",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = insights.crowdSummary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    Text(
                        text = "本地 ${insights.totalInteractions} 次",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
            insights.nodes.forEach { node ->
                InteractionHeatNodeRow(
                    node = node,
                    durationMs = insights.durationMs,
                    isPeak = node.nodeId == insights.peakNodeId,
                    onSeekTo = onSeekTo,
                )
            }
        }
    }
}

@Composable
private fun InteractionHeatNodeRow(
    node: InteractionHeatNode,
    durationMs: Long,
    isPeak: Boolean,
    onSeekTo: (Long) -> Unit,
) {
    val timelineFraction = if (durationMs > 0L) {
        (node.triggerMs.toFloat() / durationMs.toFloat()).coerceIn(0.02f, 0.98f)
    } else {
        0f
    }
    val heatFraction = (node.heatScore.coerceIn(0, 100) / 100f).coerceAtLeast(0.04f)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onSeekTo(node.triggerMs) },
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                shape = CircleShape,
                color = if (isPeak) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondaryContainer,
            ) {
                Text(
                    text = node.effectText.ifBlank { "点" },
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                    style = MaterialTheme.typography.labelLarge,
                    color = if (isPeak) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSecondaryContainer,
                    fontWeight = FontWeight.Bold,
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "${formatPlaybackTime(node.triggerMs)} · ${node.badgeText.ifBlank { node.style }}",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = if (isPeak) FontWeight.SemiBold else FontWeight.Normal,
                )
                Text(
                    text = crowdHeatText(node),
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                )
            }
            Text(
                text = "${node.heatScore}",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(10.dp)
                .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(20.dp))
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(timelineFraction)
                    .height(10.dp)
                    .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.20f), RoundedCornerShape(20.dp))
            )
            Box(
                modifier = Modifier
                    .fillMaxWidth(heatFraction)
                    .height(10.dp)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.72f), RoundedCornerShape(20.dp))
            )
        }
        val topOptions = node.options.sortedByDescending { it.percent }.take(3)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            topOptions.forEach { option ->
                CrowdOptionChip(
                    modifier = Modifier.weight(1f),
                    option = option,
                )
            }
        }
    }
}

private fun crowdHeatText(node: InteractionHeatNode): String {
    val topOption = node.options.maxByOrNull { it.percent }
    return if (topOption != null && topOption.percent > 0) {
        "此处 ${topOption.percent}% 用户也选「${topOption.optionText.ifBlank { topOption.optionId }}」"
    } else {
        node.title
    }
}

@Composable
private fun CrowdOptionChip(
    modifier: Modifier = Modifier,
    option: InteractionOptionStat,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(
                text = option.optionText.ifBlank { option.optionId },
                style = MaterialTheme.typography.labelSmall,
                maxLines = 1,
            )
            Text(
                text = "${option.percent}%",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun FeedbackOverlay(
    modifier: Modifier = Modifier,
    result: InteractionSubmitResult,
    node: InteractionNode?,
    onDismiss: () -> Unit,
) {
    val isGiftStyle = node?.visualStyle in setOf("爽点气泡", "笑出鹅叫", "弹幕冲浪")
    val isBoostStyle = node?.visualStyle == "加速包"
    Card(
        modifier = modifier
            .widthIn(max = if (isGiftStyle || isBoostStyle) 280.dp else 360.dp)
            .padding(8.dp),
        shape = RoundedCornerShape(if (isGiftStyle) 28.dp else 8.dp),
        colors = CardDefaults.cardColors(
            containerColor = when {
                isBoostStyle -> MaterialTheme.colorScheme.tertiaryContainer
                isGiftStyle -> MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.96f)
                else -> MaterialTheme.colorScheme.primaryContainer
            }
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            horizontalAlignment = if (isGiftStyle || isBoostStyle) Alignment.CenterHorizontally else Alignment.Start,
        ) {
            if (isGiftStyle) {
                Text(
                    text = "${node?.effectText?.ifBlank { "赞" } ?: "赞"} ×3 ×8 ×12",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "已上屏互动",
                    style = MaterialTheme.typography.labelLarge,
                )
            } else if (isBoostStyle) {
                Text(
                    text = "加速包已点亮",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "×2 能量补给",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.tertiary,
                )
            } else {
                Text(
                    text = "互动反馈",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Text(
                text = result.feedbackText,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = result.rewardText,
                style = MaterialTheme.typography.bodySmall
            )
            if (result.aggregate.isNotEmpty()) {
                Text(
                    text = "选择占比：" + result.aggregate.entries.joinToString(" / ") {
                        "${it.key} ${it.value}%"
                    },
                    style = MaterialTheme.typography.bodySmall
                )
            }
            if (result.nextActionType == "BRANCH_SEGMENT") {
                Text(
                    text = "已切换到插片视频，播放完成后会回到主线节点。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary
                )
            }
            TextButton(
                onClick = onDismiss,
                modifier = Modifier.align(Alignment.End)
            ) {
                Text(text = "继续观看")
            }
        }
    }
}

@Composable
private fun InteractionHistoryPanel(records: List<InteractionLocalRecord>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(
                text = "本地互动记录",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "已保存 ${records.size} 条最近记录",
                style = MaterialTheme.typography.bodySmall
            )
            records.take(3).forEach { record ->
                Text(
                    text = "• ${record.nodeTitle} / ${record.optionText} / ${record.nextActionType}",
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
private fun LoadingPanel(
    modifier: Modifier = Modifier,
    message: String,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        CircularProgressIndicator()
        Spacer(modifier = Modifier.height(12.dp))
        Text(text = message)
    }
}

@Composable
private fun ErrorPanel(
    modifier: Modifier = Modifier,
    message: String,
    onRetry: (() -> Unit)? = null,
) {
    Column(
        modifier = modifier.padding(16.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = message,
            color = MaterialTheme.colorScheme.error
        )
        if (onRetry != null) {
            TextButton(onClick = onRetry) {
                Text(text = "重试")
            }
        }
    }
}

@Composable
private fun CollapsiblePlotSummary(
    title: String,
    text: String,
    collapsedMaxLines: Int,
    modifier: Modifier = Modifier,
) {
    val cleanedText = text.trim()
    var expanded by rememberSaveable(cleanedText) { mutableStateOf(false) }
    val canToggle = cleanedText.length > 56
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
                shape = RoundedCornerShape(14.dp),
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = cleanedText,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = if (expanded || !canToggle) Int.MAX_VALUE else collapsedMaxLines,
            overflow = TextOverflow.Ellipsis,
        )
        if (canToggle) {
            TextButton(
                onClick = { expanded = !expanded },
                modifier = Modifier.align(Alignment.End),
                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 0.dp),
            ) {
                Text(text = if (expanded) "收起" else "展开")
            }
        }
    }
}

@Composable
private fun DramaCard(
    drama: HomeDramaCard,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.72f)
        )
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            DramaCoverPoster(
                title = drama.title,
                coverUrl = drama.coverUrl,
                visual = drama.coverVisual,
                latestEpisodeNo = drama.latestEpisodeNo,
                compact = true,
            )
            Text(
                text = drama.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun DetailHeader(
    detail: DramaDetailModel,
    episodes: List<EpisodeCard>,
    onEpisodeClick: (EpisodeCard) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            DramaCoverPoster(
                title = detail.title,
                coverUrl = detail.coverUrl,
                visual = detail.coverVisual,
                latestEpisodeNo = detail.latestEpisodeNo,
                showLatestBadge = false,
            )
            Text(
                text = detail.title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold
            )
            CollapsiblePlotSummary(
                title = "剧情简介",
                text = detail.description,
                collapsedMaxLines = 4,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                detail.tags.take(3).forEach { tag ->
                    Surface(
                        shape = RoundedCornerShape(20.dp),
                        color = MaterialTheme.colorScheme.secondaryContainer
                    ) {
                        Text(
                            text = tag,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelMedium
                        )
                    }
                }
            }
            HorizontalDivider()
            Text(
                text = "角色",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            detail.characters.forEach { character ->
                Text(
                    text = "• ${character.name}",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            HorizontalDivider()
            EpisodeNumberStrip(
                episodes = episodes,
                onClick = onEpisodeClick,
            )
        }
    }
}

@Composable
private fun StorySummaryCacheCard(
    state: LoadState<StorySummaryCacheStatus>,
    onRefresh: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = "剧情简介缓存",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "整剧概括和分集概括分开缓存，刷新失败不会覆盖最后一次成功产物",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                TextButton(onClick = onRefresh) {
                    Text(text = "刷新缓存")
                }
            }
            when (state) {
                LoadState.Loading -> {
                    Text(text = "正在读取缓存状态", style = MaterialTheme.typography.bodyMedium)
                }

                is LoadState.Error -> {
                    Text(text = state.message, color = MaterialTheme.colorScheme.error)
                }

                is LoadState.Success -> {
                    val result = state.data
                    Surface(
                        shape = RoundedCornerShape(999.dp),
                        color = if (result.status == "ok") {
                            MaterialTheme.colorScheme.tertiaryContainer
                        } else {
                            MaterialTheme.colorScheme.errorContainer
                        }
                    ) {
                        Text(
                            text = buildString {
                                append("状态：")
                                append(result.status)
                                append(" · 来源：")
                                append(result.source.ifBlank { "未知" })
                                append(" · 生成于：")
                                append(formatReadableTimestamp(result.generatedAtMs))
                            },
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            style = MaterialTheme.typography.labelMedium,
                            color = if (result.status == "ok") {
                                MaterialTheme.colorScheme.onTertiaryContainer
                            } else {
                                MaterialTheme.colorScheme.onErrorContainer
                            }
                        )
                    }
                    Text(
                        text = "模型：${result.modelName.ifBlank { "未知" }} · 耗时：${result.latencyMs} ms · Prompt：${result.promptVersion}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text(
                        text = if (result.status == "ok") {
                            "当前展示的是最后一次成功产物"
                        } else {
                            "当前展示仍是成功缓存，失败结果不会覆盖它"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    if (result.latestAttempt.status != "missing") {
                        Text(
                            text = "最近尝试：${result.latestAttempt.status} / ${result.latestAttempt.source} / ${result.latestAttempt.latencyMs} ms",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        if (result.latestAttempt.degradeReason.isNotBlank()) {
                            Text(
                                text = "尝试降级：${result.latestAttempt.degradeReason}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                    if (result.degradeReason.isNotBlank()) {
                        Text(
                            text = "降级原因：${result.degradeReason}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    CollapsiblePlotSummary(
                        title = "整剧概括",
                        text = result.dramaDescription,
                        collapsedMaxLines = 4,
                    )
                    if (result.episodes.isNotEmpty()) {
                        Text(
                            text = "分集概括",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                        result.episodes.take(5).forEach { episode ->
                            CollapsiblePlotSummary(
                                title = "第${episode.episodeNo}集",
                                text = episode.summary,
                                collapsedMaxLines = 2,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailMoreContentPanel(
    storySummaryState: LoadState<StorySummaryCacheStatus>,
    savedMoments: List<ShareableMoment>,
    onRefreshSummary: () -> Unit,
    onOpenMoment: (ShareableMoment) -> Unit,
) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f)
        )
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded },
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        text = "更多内容",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = "剧情缓存、高能收藏等收起展示，详情页优先保留主信息和选集",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = if (expanded) "收起" else "展开",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    StorySummaryCacheCard(
                        state = storySummaryState,
                        onRefresh = onRefreshSummary,
                    )
                    if (savedMoments.isNotEmpty()) {
                        Text(
                            text = "已收藏高能片段",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                        savedMoments.take(4).forEach { moment ->
                            ShareableMomentCard(
                                moment = moment,
                                onClick = { onOpenMoment(moment) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EpisodeNumberStrip(
    episodes: List<EpisodeCard>,
    onClick: (EpisodeCard) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = "选集",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(horizontal = 2.dp),
        ) {
            items(episodes, key = { it.episodeId }) { episode ->
                Surface(
                    modifier = Modifier
                        .size(width = 54.dp, height = 46.dp)
                        .clickable { onClick(episode) },
                    shape = RoundedCornerShape(14.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                    tonalElevation = 2.dp,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(
                            text = episode.episodeNo.toString(),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun EpisodeItemCard(
    episode: EpisodeCard,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                text = episode.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            CollapsiblePlotSummary(
                title = "本集剧情",
                text = episode.summary,
                collapsedMaxLines = 2,
            )
            Text(
                text = "时长约 ${episode.durationMs / 1000}s",
                style = MaterialTheme.typography.bodySmall
            )
            TextButton(onClick = onClick) {
                Text(text = "播放")
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleLarge,
        fontWeight = FontWeight.SemiBold
    )
}

@Composable
private fun AiEntryCard(
    onOpenAi: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "AI 体验入口",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "进入后可以直接生成剧情摘要、互动反馈、标签抽取和内容审核结果。",
                style = MaterialTheme.typography.bodyMedium
            )
            TextButton(onClick = onOpenAi) {
                Text(text = "立即体验")
            }
        }
    }
}

@Composable
private fun DemoRouteCard(
    state: LoadState<DemoRoutePlan>,
    onStart: (DemoRoutePlan) -> Unit,
    onOpenAi: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.72f)
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "答辩演示路线",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            when (state) {
                LoadState.Loading -> Text(
                    text = "正在准备推荐演示路线",
                    style = MaterialTheme.typography.bodyMedium,
                )

                is LoadState.Error -> Text(
                    text = state.message,
                    color = MaterialTheme.colorScheme.error,
                )

                is LoadState.Success -> {
                    val route = state.data
                    Text(
                        text = route.title,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        text = "入口：${route.entry.title} · ${route.entry.episodeId} · ${formatPlaybackTime(route.entry.startMs)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                    Text(
                        text = "来源 ${route.source} · 重启可演示 ${if (route.checks.restartSafe) "是" else "否"} · 证据图谱 ${if (route.checks.evidenceGraphAvailable) "可用" else "降级"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    route.steps.take(6).forEach { step ->
                        Text(
                            text = "${step.order}. ${step.title} · ${step.status}",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { onStart(route) }) {
                            Text(text = "开始演示")
                        }
                        TextButton(onClick = onOpenAi) {
                            Text(text = "打开 AI 任务中心")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DefenseDemoModeCard(
    enabled: Boolean,
    state: LoadState<DefenseDemoModeStatus>,
    onToggle: () -> Unit,
    onStart: (DefenseDemoModeStatus) -> Unit,
    onOpenAi: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (enabled) {
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.78f)
            } else {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.62f)
            }
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "答辩演示模式",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                TextButton(onClick = onToggle) {
                    Text(text = if (enabled) "已开启" else "开启")
                }
            }
            when (state) {
                LoadState.Loading -> Text(
                    text = "正在读取演示模式状态",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                is LoadState.Error -> Text(
                    text = state.message,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )

                is LoadState.Success -> {
                    val mode = state.data
                    Text(
                        text = mode.description.ifBlank { "固定演示路线，优先展示稳定缓存和可用产物。" },
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text(
                        text = "来源 ${mode.contentSource.ifBlank { "unknown" }} · 策略 ${homeHighlightStrategyLabel(mode.fixedStrategy)} · 入口 ${mode.entry.episodeId} ${formatPlaybackTime(mode.entry.startMs)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "兜底：首页 ${if (mode.fallbacks.homeFallbackAvailable) "可用" else "缺失"} · SQLite ${if (mode.fallbacks.sqliteBacked) "可用" else "缺失"} · 最后成功产物 ${if (mode.fallbacks.lastSuccessArtifactAvailable) "可用" else "待生成"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    mode.quickSteps.take(6).forEachIndexed { index, step ->
                        Text(
                            text = "${index + 1}. ${step.title} · ${step.status}",
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { onStart(mode) },
                            enabled = mode.entry.episodeId.isNotBlank(),
                        ) {
                            Text(text = "从固定入口开始")
                        }
                        TextButton(onClick = onOpenAi) {
                            Text(text = "看任务中心")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ShareableMomentCard(
    moment: ShareableMoment,
    featured: Boolean = false,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (featured) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f)
            }
        )
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (featured) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.tertiaryContainer,
                ) {
                    Text(
                        text = "首推高能",
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
            }
            Text(
                text = "${moment.episodeTitle.ifBlank { "第${moment.episodeNo}集" }} · ${formatPlaybackTime(moment.startMs)}",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = moment.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = moment.hookText,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (featured) {
                Text(
                    text = "从这里开始回看，直接定位到 ${formatPlaybackTime(moment.startMs)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = "热度 ${moment.heatScore} · 来源 ${moment.source}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (moment.selectionStrategy.isNotBlank()) {
                Text(
                    text = "挑片策略 ${homeHighlightStrategyLabel(moment.selectionStrategy)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            TextButton(onClick = onClick) {
                Text(text = "直接回看")
            }
        }
    }
}

private data class DramaDetailScreenState(
    val detail: DramaDetailModel,
    val episodes: List<EpisodeCard>,
    val savedMoments: List<ShareableMoment>,
)

private data class PlayerScreenState(
    val playbackEpisode: PlaybackEpisode,
    val interactionConfig: InteractionConfig,
    val episodeSummary: String,
)

private data class PlayerDanmakuEntry(
    val entryId: String,
    val text: String,
    val lane: Int,
    val isUserGenerated: Boolean,
)

private data class PlayerComment(
    val author: String,
    val content: String,
    val likeCount: Int,
    val replyCount: Int,
    val dislikeCount: Int = 0,
)

private const val PLAYER_DANMAKU_LANE_COUNT = 6
private const val PLAYER_DANMAKU_MAX_ACTIVE = 24

private fun buildInitialDanmakuTexts(interactionConfig: InteractionConfig): List<String> {
    val nodeTexts = interactionConfig.nodes.mapNotNull { node ->
        listOf(
            node.effectText,
            node.badgeText,
            node.promptText,
            node.title,
        ).firstOrNull { it.isNotBlank() }
    }.distinct().take(4)
    return buildList {
        add("好帅")
        add("这段绝了")
        add("前方高能")
        add("弹幕护体")
        add("直接起飞")
        addAll(nodeTexts)
    }.distinct().take(PLAYER_DANMAKU_MAX_ACTIVE)
}

private fun buildPlayerEpisodeIntro(
    playbackEpisode: PlaybackEpisode,
    interactionConfig: InteractionConfig,
    episodeSummary: String,
): String {
    if (episodeSummary.isNotBlank()) {
        return episodeSummary
    }
    val keyNode = interactionConfig.nodes.minByOrNull { node -> node.triggerMs }
    return keyNode?.let { node ->
        listOf(
            node.promptText,
            node.title,
            node.effectText,
        ).firstOrNull { it.isNotBlank() }
    }?.takeIf { it.isNotBlank() }
        ?: "本集围绕${playbackEpisode.title}展开，人物关系和身份冲突持续升级，关键选择会影响后续高能片段。"
}

private fun dramaIdFromEpisodeId(episodeId: String): String {
    return episodeId.substringBeforeLast("_ep", missingDelimiterValue = "tainai3")
}

private fun seedEngagementCount(seed: String, minValue: Int, maxValue: Int): Int {
    val range = (maxValue - minValue).coerceAtLeast(1)
    return minValue + (abs(seed.hashCode()) % range)
}

private fun buildShortPlayPlayer(
    context: Context,
    playUrl: String,
    initialPositionMs: Long,
): ExoPlayer {
    val appContext = context.applicationContext
    val httpDataSourceFactory = DefaultHttpDataSource.Factory()
        .setAllowCrossProtocolRedirects(true)
        .setConnectTimeoutMs(8_000)
        .setReadTimeoutMs(30_000)
        .setUserAgent("aigc-shortplay-demo")
    val upstreamDataSourceFactory = DefaultDataSource.Factory(appContext, httpDataSourceFactory)
    val cachedDataSourceFactory = CacheDataSource.Factory()
        .setCache(PlaybackCacheHolder.get(appContext))
        .setUpstreamDataSourceFactory(upstreamDataSourceFactory)
        .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
    val loadControl = DefaultLoadControl.Builder()
        .setBufferDurationsMs(
            15_000,
            90_000,
            1_500,
            4_000,
        )
        .build()

    return ExoPlayer.Builder(appContext)
        .setMediaSourceFactory(DefaultMediaSourceFactory(cachedDataSourceFactory))
        .setLoadControl(loadControl)
        .build()
        .apply {
            repeatMode = Player.REPEAT_MODE_OFF
            setMediaItem(MediaItem.fromUri(playUrl))
            if (initialPositionMs > 0L) {
                seekTo(initialPositionMs)
            }
            prepare()
            playWhenReady = true
        }
}

private fun retryPlaybackWithUrl(
    exoPlayer: ExoPlayer,
    playUrl: String,
    resumePositionMs: Long,
) {
    val safePositionMs = resumePositionMs.coerceAtLeast(0L)
    exoPlayer.stop()
    exoPlayer.clearMediaItems()
    exoPlayer.setMediaItem(MediaItem.fromUri(playUrl))
    if (safePositionMs > 0L) {
        exoPlayer.seekTo(safePositionMs)
    }
    exoPlayer.prepare()
    exoPlayer.play()
}

private fun playbackUrlType(playUrl: String): String {
    val normalized = playUrl.lowercase(Locale.ROOT)
    return when {
        normalized.contains(".m3u8") -> "hls"
        normalized.contains("/aigc-inserts/") -> "aigc_insert"
        normalized.endsWith(".mp4") || normalized.contains("/media/episodes/") -> "mp4"
        else -> "unknown"
    }
}

private object PlaybackCacheHolder {
    private const val MAX_CACHE_BYTES = 256L * 1024L * 1024L

    @Volatile
    private var cache: SimpleCache? = null

    fun get(context: Context): SimpleCache {
        val appContext = context.applicationContext
        return cache ?: synchronized(this) {
            cache ?: SimpleCache(
                File(appContext.cacheDir, "shortplay-video-cache"),
                LeastRecentlyUsedCacheEvictor(MAX_CACHE_BYTES),
                StandaloneDatabaseProvider(appContext),
            ).also { cache = it }
        }
    }
}

private fun ExoPlayer.safePositionMs(): Long {
    return currentPosition.coerceAtLeast(0L)
}

private fun ExoPlayer.safeDurationMs(): Long {
    val currentDuration = duration
    return if (currentDuration == C.TIME_UNSET || currentDuration < 0L) {
        0L
    } else {
        currentDuration
    }
}

private fun formatPlaybackTime(milliseconds: Long): String {
    val totalSeconds = (milliseconds / 1000L).coerceAtLeast(0L)
    val minutes = totalSeconds / 60L
    val seconds = totalSeconds % 60L
    return "%02d:%02d".format(minutes, seconds)
}

private fun formatCompactCount(count: Int): String {
    return when {
        count >= 10_000 -> String.format(Locale.getDefault(), "%.1f万", count / 10_000f)
        count >= 1_000 -> String.format(Locale.getDefault(), "%.1fk", count / 1_000f)
        else -> count.coerceAtLeast(0).toString()
    }
}

private fun formatReadableTimestamp(milliseconds: Long): String {
    if (milliseconds <= 0L) {
        return "未知"
    }
    val formatter = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
    return formatter.format(Date(milliseconds))
}

private fun formatConfidenceScore(confidence: Double): String {
    val clamped = confidence.coerceIn(0.0, 1.0)
    return String.format(Locale.getDefault(), "%.2f", clamped)
}

private fun playbackStateLabel(state: Int): String {
    return when (state) {
        Player.STATE_IDLE -> "IDLE 待准备"
        Player.STATE_BUFFERING -> "BUFFERING 缓冲中"
        Player.STATE_READY -> "READY 可播放"
        Player.STATE_ENDED -> "ENDED 已播完"
        else -> "UNKNOWN $state"
    }
}

private fun resolveNextEpisodeId(episodeId: String): String? {
    val match = Regex("^(.*?)(\\d+)$").find(episodeId) ?: return null
    val prefix = match.groupValues[1]
    val digits = match.groupValues[2]
    val nextValue = digits.toLongOrNull()?.plus(1) ?: return null
    return prefix + nextValue.toString().padStart(digits.length, '0')
}

private fun episodeNoFromEpisodeId(episodeId: String): Int {
    return Regex("(\\d+)$")
        .find(episodeId)
        ?.groupValues
        ?.getOrNull(1)
        ?.toIntOrNull()
        ?: 1
}

private fun pageViewEvent(
    screenName: String,
    dramaId: String? = null,
    episodeId: String? = null,
): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = "page_view",
        screenName = screenName,
        dramaId = dramaId,
        episodeId = episodeId,
        clientTsMs = System.currentTimeMillis(),
    )
}

private fun homeContentSourceEvent(
    dramaId: String,
    contentSource: String,
): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = "home_content_source",
        screenName = "home",
        dramaId = dramaId,
        clientTsMs = System.currentTimeMillis(),
        properties = mapOf("contentSource" to contentSource),
    )
}

private fun homeHighlightMomentEvent(
    eventName: String,
    moment: ShareableMoment,
    rank: Int,
): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = eventName,
        screenName = "home",
        dramaId = moment.dramaId,
        episodeId = moment.episodeId,
        progressMs = moment.startMs,
        clientTsMs = System.currentTimeMillis(),
        properties = linkedMapOf(
            "momentId" to moment.momentId,
            "rank" to rank.toString(),
            "episodeNo" to moment.episodeNo.toString(),
            "episodeTitle" to moment.episodeTitle,
            "startMs" to moment.startMs.toString(),
            "endMs" to moment.endMs.toString(),
            "heatScore" to moment.heatScore.toString(),
            "source" to moment.source,
            "selectionStrategy" to moment.selectionStrategy,
        ),
    )
}

private fun nextHomeHighlightStrategy(current: String): String {
    val strategies = listOf(
        "hybrid",
        "interaction_first",
        "danmaku_first",
        "ai_evidence_first",
        "heat_score_desc_v1",
        "episode_spread_v1",
        "recent_episode_v1",
    )
    val nextIndex = (strategies.indexOf(current).takeIf { it >= 0 } ?: 0) + 1
    return strategies[nextIndex % strategies.size]
}

private fun homeHighlightStrategyLabel(strategy: String): String {
    return when (strategy) {
        "hybrid" -> "混合策略"
        "interaction_first" -> "互动优先"
        "danmaku_first" -> "弹幕优先"
        "ai_evidence_first" -> "AI证据优先"
        "episode_spread_v1" -> "分集均衡"
        "recent_episode_v1" -> "近期优先"
        else -> "热度优先"
    }
}

private fun homeContentSourceLabel(source: String): String {
    return when (source) {
        "cache" -> "后端缓存"
        "backend" -> "后端实时"
        "local_fallback" -> "本地兜底"
        else -> source.ifBlank { "未知" }
    }
}

private fun interactionComponentProperties(
    node: InteractionNode,
    option: InteractionOption? = null,
): Map<String, String> {
    val properties = linkedMapOf(
        "componentType" to node.componentType,
        "visualStyle" to node.visualStyle,
        "analyticsKey" to node.analyticsKey,
        "nodeTitle" to node.title,
    )
    if (option != null) {
        properties["optionId"] = option.id
        properties["optionText"] = option.text
    }
    return properties
}

private fun interactionSubmitEvent(
    dramaId: String,
    episodeId: String,
    nodeId: String,
    optionId: String,
    optionText: String,
    nextActionType: String,
    branchSegmentId: String?,
    componentType: String,
    visualStyle: String,
    analyticsKey: String,
): TelemetryEvent {
    val properties = linkedMapOf(
        "optionId" to optionId,
        "optionText" to optionText,
        "nextActionType" to nextActionType,
        "componentType" to componentType,
        "visualStyle" to visualStyle,
        "analyticsKey" to analyticsKey,
    )
    if (!branchSegmentId.isNullOrBlank()) {
        properties["branchSegmentId"] = branchSegmentId
    }
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = "interaction_submit",
        screenName = "player",
        dramaId = dramaId,
        episodeId = episodeId,
        nodeId = nodeId,
        clientTsMs = System.currentTimeMillis(),
        properties = properties,
    )
}

private fun interactionImpressionEvent(
    dramaId: String,
    episodeId: String,
    node: InteractionNode,
): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = "interaction_impression",
        screenName = "player",
        dramaId = dramaId,
        episodeId = episodeId,
        nodeId = node.id,
        progressMs = node.triggerMs,
        clientTsMs = System.currentTimeMillis(),
        properties = linkedMapOf(
            "nodeTitle" to node.title,
            "triggerMs" to node.triggerMs.toString(),
            "componentType" to node.componentType,
            "visualStyle" to node.visualStyle,
            "analyticsKey" to node.analyticsKey,
        ),
    )
}

private fun playerBehaviorEvent(
    eventName: String,
    dramaId: String,
    episodeId: String,
    nodeId: String? = null,
    progressMs: Long? = null,
    properties: Map<String, String> = emptyMap(),
): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = eventName,
        screenName = "player",
        dramaId = dramaId,
        episodeId = episodeId,
        nodeId = nodeId,
        progressMs = progressMs,
        clientTsMs = System.currentTimeMillis(),
        properties = properties,
    )
}
