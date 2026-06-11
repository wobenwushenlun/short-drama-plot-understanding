package com.shortdrama.plotunderstanding.feature.home

import android.graphics.BitmapFactory
import android.graphics.Color as AndroidColor
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
internal fun DramaCoverPoster(
    title: String,
    coverUrl: String,
    visual: CoverVisualMetadata,
    latestEpisodeNo: Int,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    showLatestBadge: Boolean = true,
) {
    val colors = visual.palette.toPosterColors()
    val imageUrl = visual.layers.portraitUrl.ifBlank { coverUrl }
    val imageBitmap by produceState<ImageBitmap?>(initialValue = null, key1 = imageUrl) {
        value = loadRemoteCoverImage(imageUrl)
    }
    val posterShape = RoundedCornerShape(if (compact) 22.dp else 28.dp)
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(if (compact) 0.72f else 1.34f),
        shape = posterShape,
        color = colors.primary,
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.linearGradient(
                        listOf(
                            colors.primary,
                            colors.secondary,
                            colors.accent.copy(alpha = 0.78f),
                        )
                    )
                )
        ) {
            when {
                imageBitmap != null -> {
                    Image(
                        bitmap = imageBitmap!!,
                        contentDescription = title,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop,
                    )
                }
            }
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                Color.Transparent,
                                Color.Transparent,
                                Color.Black.copy(alpha = if (compact) 0.44f else 0.36f),
                            )
                        )
                    )
            )
            if (compact) {
                PosterCompactBadges(
                    heatLabel = visual.layers.heatLabel,
                    latestLabel = visual.layers.latestLabel.ifBlank { latestEpisodeLabel(latestEpisodeNo) },
                    accent = colors.accent,
                    modifier = Modifier
                        .align(Alignment.BottomStart)
                        .padding(10.dp),
                )
            } else {
                PosterTopBadges(
                    latestEpisodeNo = latestEpisodeNo,
                    identityLabel = visual.layers.identityLabel,
                    latestLabel = visual.layers.latestLabel,
                    showLatestBadge = showLatestBadge,
                    accent = colors.accent,
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(14.dp),
                )
            }
        }
    }
}

@Composable
private fun PosterTopBadges(
    latestEpisodeNo: Int,
    identityLabel: String,
    latestLabel: String,
    showLatestBadge: Boolean,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (identityLabel.isNotBlank()) {
            PosterPill(text = identityLabel, color = accent)
        }
        if (showLatestBadge) {
            val label = latestLabel.ifBlank { latestEpisodeLabel(latestEpisodeNo) }
            if (label.isNotBlank()) {
                PosterPill(text = label, color = Color.White.copy(alpha = 0.86f))
            }
        }
    }
}

@Composable
@OptIn(ExperimentalFoundationApi::class)
private fun PosterCompactBadges(
    heatLabel: String,
    latestLabel: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    val tickerItems = listOf(normalizeHeatLabel(heatLabel), latestLabel).filter { it.isNotBlank() }
    if (tickerItems.isEmpty()) {
        return
    }
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = Color.Black.copy(alpha = 0.22f),
        modifier = modifier
            .fillMaxWidth(0.86f)
            .border(
                width = 1.dp,
                color = accent.copy(alpha = 0.42f),
                shape = RoundedCornerShape(999.dp),
            ),
    ) {
        Text(
            text = (tickerItems.joinToString("   ·   ") + "      ").repeat(3),
            modifier = Modifier
                .padding(horizontal = 10.dp, vertical = 5.dp)
                .basicMarquee(
                    iterations = Int.MAX_VALUE,
                    initialDelayMillis = 300,
                ),
            style = MaterialTheme.typography.labelMedium,
            color = Color.White,
            maxLines = 1,
        )
    }
}

private fun latestEpisodeLabel(latestEpisodeNo: Int): String {
    return if (latestEpisodeNo > 0) "更新至第${latestEpisodeNo}集" else ""
}

private fun normalizeHeatLabel(label: String): String {
    return label.replace("想看", "观看")
}

@Composable
private fun PosterPill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = Color.Black.copy(alpha = 0.24f),
        modifier = modifier.border(
            width = 1.dp,
            color = color.copy(alpha = 0.46f),
            shape = RoundedCornerShape(999.dp),
        ),
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.labelMedium,
            color = Color.White,
            maxLines = 1,
        )
    }
}

private data class PosterColors(
    val primary: Color,
    val secondary: Color,
    val accent: Color,
)

private fun CoverPalette.toPosterColors(): PosterColors {
    return PosterColors(
        primary = parsePosterColor(primary, Color(0xFF25130F)),
        secondary = parsePosterColor(secondary, Color(0xFF8A4F22)),
        accent = parsePosterColor(accent, Color(0xFFF8D36D)),
    )
}

private fun parsePosterColor(value: String, fallback: Color): Color {
    return try {
        Color(AndroidColor.parseColor(value))
    } catch (_: IllegalArgumentException) {
        fallback
    }
}

private suspend fun loadRemoteCoverImage(coverUrl: String): ImageBitmap? {
    val normalizedUrl = coverUrl.trim()
    if (normalizedUrl.isBlank()) {
        return null
    }
    remoteCoverBitmapCache[normalizedUrl]?.let { return it }
    return withContext(Dispatchers.IO) {
        runCatching {
            val connection = URL(normalizedUrl).openConnection().apply {
                connectTimeout = 3_000
                readTimeout = 5_000
            }
            connection.getInputStream().use { input ->
                BitmapFactory.decodeStream(input)?.asImageBitmap()?.also { bitmap ->
                    remoteCoverBitmapCache[normalizedUrl] = bitmap
                }
            }
        }.getOrNull()
    }
}

private val remoteCoverBitmapCache = ConcurrentHashMap<String, ImageBitmap>()
