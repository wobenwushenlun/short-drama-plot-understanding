@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.contest.aigc.shortplay.feature.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.contest.aigc.shortplay.core.ui.AigcModeToggle
import com.contest.aigc.shortplay.core.ui.AigcScreenScaffold
import com.contest.aigc.shortplay.core.ui.AigcThemeMode
import java.util.UUID

private sealed interface HistoryLoadState<out T> {
    data object Loading : HistoryLoadState<Nothing>

    data class Success<T>(val data: T) : HistoryLoadState<T>

    data class Error(val message: String) : HistoryLoadState<Nothing>
}
@Composable
fun WatchHistoryRoute(
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onBack: () -> Unit,
    onOpenEpisode: (String, Long) -> Unit,
    repository: ShortPlayRepository? = null,
) {
    val resolvedRepository = repository ?: rememberRepository()
    val telemetryDispatcher = remember(resolvedRepository) { BackendTelemetryDispatcher(resolvedRepository) }
    val context = LocalContext.current
    var retryTick by remember { mutableStateOf(0) }
    val state by produceState<HistoryLoadState<List<WatchHistoryItem>>>(
        initialValue = HistoryLoadState.Loading,
        retryTick,
        resolvedRepository
    ) {
        value = try {
            HistoryLoadState.Success(resolvedRepository.loadWatchHistory())
        } catch (throwable: Throwable) {
            HistoryLoadState.Error(throwable.message ?: "观看历史加载失败")
        }
    }

    LaunchedEffect(resolvedRepository) {
        telemetryDispatcher.track(
            context = context,
            events = listOf(pageViewEvent("watch_history"))
        )
    }

    AigcScreenScaffold(
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    scrolledContainerColor = Color.Transparent,
                ),
                title = { Text(text = "观看历史") },
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
            HistoryLoadState.Loading -> LoadingHistoryPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = "正在加载最近观看记录"
            )

            is HistoryLoadState.Error -> ErrorHistoryPanel(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                message = current.message,
                onRetry = { retryTick += 1 }
            )

            is HistoryLoadState.Success -> LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(current.data) { item ->
                    WatchHistoryCard(
                        item = item,
                        onPlay = {
                            onOpenEpisode(
                                item.episodeId,
                                if (item.isCompleted) 0L else item.lastProgressMs.coerceAtLeast(0L)
                            )
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun WatchHistoryCard(
    item: WatchHistoryItem,
    onPlay: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onPlay),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = item.dramaTitle,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = item.episodeTitle,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                text = "进度 ${item.lastProgressMs / 1000}s / ${item.durationMs / 1000}s",
                style = MaterialTheme.typography.bodySmall
            )
            Text(
                text = if (item.isCompleted) "状态：已看完" else "状态：继续观看",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.primary
            )
            Button(onClick = onPlay) {
                Text(text = "继续播放")
            }
        }
    }
}

@Composable
private fun LoadingHistoryPanel(
    modifier: Modifier = Modifier,
    message: String,
) {
    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        CircularProgressIndicator()
        Text(text = message)
    }
}

@Composable
private fun ErrorHistoryPanel(
    modifier: Modifier = Modifier,
    message: String,
    onRetry: () -> Unit,
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
        TextButton(onClick = onRetry) {
            Text(text = "重试")
        }
    }
}

private fun pageViewEvent(screenName: String): TelemetryEvent {
    return TelemetryEvent(
        eventId = UUID.randomUUID().toString(),
        eventName = "page_view",
        screenName = screenName,
        clientTsMs = System.currentTimeMillis(),
    )
}
