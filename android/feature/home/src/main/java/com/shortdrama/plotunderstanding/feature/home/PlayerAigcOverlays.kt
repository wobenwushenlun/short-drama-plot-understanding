package com.shortdrama.plotunderstanding.feature.home

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.provider.MediaStore
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext


@Composable
internal fun StoryContinuationOverlay(
    modifier: Modifier = Modifier,
    state: LoadState<AiStoryContinuationResult>?,
    userIntent: String,
    onUserIntentChange: (String) -> Unit,
    onGenerate: () -> Unit,
    onPlay: (AiStoryContinuationResult) -> Unit,
    onGenerateCheckin: () -> Unit,
    onDismiss: () -> Unit,
) {
    Card(
        modifier = modifier
            .widthIn(max = 340.dp)
            .padding(16.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = "本集已播完",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "生成一段基于本集剧情理解的幻想续写，不代表原剧正式内容。",
                style = MaterialTheme.typography.bodySmall,
            )
            CreativeIntentInput(
                value = userIntent,
                onValueChange = onUserIntentChange,
                label = "你希望下一幕怎么发展？",
                placeholder = "例如：女主黑化反击，但不要马上原谅男主",
            )
            when (state) {
                null -> {
                    Text(
                        text = "由 Doubao 续写下一幕，并生成可播放的短片预演。",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth()) {
                        Text(text = "生成下一幕")
                    }
                }

                LoadState.Loading -> {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp))
                        Text(text = "正在生成情节续写与预演片段")
                    }
                }

                is LoadState.Error -> {
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth()) {
                        Text(text = "重新生成")
                    }
                }

                is LoadState.Success -> {
                    val result = state.data
                    Text(
                        text = result.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(text = result.summary, style = MaterialTheme.typography.bodyMedium)
                    Text(
                        text = "场景：${result.sceneDirection}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    result.dialogueLines.take(2).forEach { line ->
                        Text(text = line, style = MaterialTheme.typography.bodySmall)
                    }
                    Text(
                        text = result.viewerHook,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    if (result.degradeReason != null) {
                        Text(
                            text = "已使用降级生成结果",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        text = "生成链路：${result.providerName.ifBlank { "unknown" }} / ${result.providerMode.ifBlank { "template" }}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (result.referenceStatus.isNotBlank()) {
                        Text(
                            text = "参考帧状态：${result.referenceStatus}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (result.remoteAttemptReason.isNotBlank()) {
                        Text(
                            text = "远端降级原因：${result.remoteAttemptReason}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Button(
                        onClick = { onPlay(result) },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = result.mediaUrl.isNotBlank(),
                    ) {
                        Text(text = "播放 AIGC 续写")
                    }
                }
            }
            TextButton(onClick = onGenerateCheckin, modifier = Modifier.fillMaxWidth()) {
                Text(text = "生成本集反转打卡图")
            }
            TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.End)) {
                Text(text = "关闭")
            }
        }
    }
}


@Composable
internal fun CheckinCardOverlay(
    modifier: Modifier = Modifier,
    state: LoadState<AiCheckinCardResult>?,
    selectedStyle: String,
    userIntent: String,
    onUserIntentChange: (String) -> Unit,
    onStyleSelected: (String) -> Unit,
    onGenerate: () -> Unit,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var savingImage by remember { mutableStateOf(false) }
    Card(
        modifier = modifier
            .widthIn(max = 340.dp)
            .heightIn(max = 560.dp)
            .padding(16.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(
            modifier = Modifier
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = "Agnes 打卡图",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "用本集剧情摘要、互动爽点和观众情绪生成分享海报，失败时自动回落为本地文本卡片。",
                style = MaterialTheme.typography.bodySmall,
            )
            CheckinStyleSelector(
                selectedStyle = selectedStyle,
                onStyleSelected = onStyleSelected,
            )
            CreativeIntentInput(
                value = userIntent,
                onValueChange = onUserIntentChange,
                label = "你希望海报呈现什么感觉？",
                placeholder = "例如：雨夜对峙、身份揭露、女主站在光里",
            )
            when (state) {
                null -> {
                    Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth()) {
                        Text(text = "生成打卡图")
                    }
                }

                LoadState.Loading -> {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp))
                        Text(text = "正在生成打卡图")
                    }
                }

                is LoadState.Error -> {
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth()) {
                        Text(text = "重新生成")
                    }
                }

                is LoadState.Success -> {
                    val result = state.data
                    val imageUrl = result.mediaAsset.localUrl
                        .ifBlank { result.mediaAsset.mediaUrl }
                        .ifBlank { result.imageUrl }
                    Text(
                        text = result.title.ifBlank { "剧情打卡海报" },
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    if (imageUrl.isNotBlank()) {
                        GeneratedCheckinImagePreview(
                            imageUrl = imageUrl,
                            title = result.title.ifBlank { "剧情打卡海报" },
                        )
                        CheckinPosterActionPills(
                            cacheStatus = result.mediaAsset.cacheStatus,
                            provider = result.provider,
                            saving = savingImage,
                            onSave = {
                                coroutineScope.launch {
                                    savingImage = true
                                    val saved = saveCheckinImageToGallery(
                                        context = context,
                                        imageUrl = imageUrl,
                                        title = result.title.ifBlank { "剧情打卡海报" },
                                    )
                                    savingImage = false
                                    Toast.makeText(
                                        context,
                                        if (saved) "打卡图已保存到相册" else "保存失败，请稍后重试",
                                        Toast.LENGTH_SHORT,
                                    ).show()
                                }
                            },
                            onShare = {
                                shareCheckinCard(
                                    context = context,
                                    title = result.title.ifBlank { "剧情打卡海报" },
                                    imageUrl = imageUrl,
                                    styleLabel = result.styleLabel.ifBlank { result.style },
                                )
                            },
                        )
                        Text(
                            text = "图片：$imageUrl",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    } else {
                        Text(
                            text = "已使用本地文本卡片兜底",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (result.mediaAsset.cacheStatus.isNotBlank()) {
                        Text(
                            text = "产物缓存：${result.mediaAsset.cacheStatus}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        text = "风格：${result.styleLabel.ifBlank { result.style }} / Provider：${result.provider} / 状态：${result.cardStatus} / ${result.cardLatencyMs} ms",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (result.cardDegradeReason.isNotBlank()) {
                        Text(
                            text = "降级原因：${result.cardDegradeReason}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        text = result.prompt,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Button(onClick = onGenerate, modifier = Modifier.fillMaxWidth()) {
                        Text(text = "再生成一张")
                    }
                }
            }
            TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.End)) {
                Text(text = "关闭")
            }
        }
    }
}

@Composable
private fun CheckinPosterActionPills(
    cacheStatus: String,
    provider: String,
    saving: Boolean,
    onSave: () -> Unit,
    onShare: () -> Unit,
) {
    val sourceLabel = cacheStatus.ifBlank { provider.ifBlank { "remote" } }
    Column(
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CheckinActionPill(
                text = if (saving) "正在保存" else "保存到相册",
                enabled = !saving,
                onClick = onSave,
            )
            CheckinActionPill(
                text = "分享给好友",
                enabled = !saving,
                onClick = onShare,
            )
        }
        CheckinActionPill(text = "来源：$sourceLabel")
    }
}

@Composable
private fun CheckinActionPill(
    text: String,
    enabled: Boolean = true,
    onClick: (() -> Unit)? = null,
) {
    Surface(
        modifier = if (onClick != null) {
            Modifier.clickable(enabled = enabled, onClick = onClick)
        } else {
            Modifier
        },
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.64f),
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
            maxLines = 1,
        )
    }
}

@Composable
private fun CreativeIntentInput(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    placeholder: String,
) {
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        OutlinedTextField(
            value = value,
            onValueChange = { onValueChange(it.take(120)) },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(text = label) },
            placeholder = { Text(text = placeholder) },
            minLines = 2,
            maxLines = 3,
            textStyle = MaterialTheme.typography.bodySmall,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            CREATIVE_INTENT_PRESETS.take(3).forEach { preset ->
                Surface(
                    modifier = Modifier.clickable { onValueChange(preset) },
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = 0.58f),
                ) {
                    Text(
                        text = preset,
                        modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                    )
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            CREATIVE_INTENT_PRESETS.drop(3).forEach { preset ->
                Surface(
                    modifier = Modifier.clickable { onValueChange(preset) },
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.surface.copy(alpha = 0.58f),
                ) {
                    Text(
                        text = preset,
                        modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                    )
                }
            }
        }
    }
}

@Composable
internal fun GeneratedCheckinImagePreview(
    imageUrl: String,
    title: String,
    modifier: Modifier = Modifier,
) {
    val imageBitmap by produceState<ImageBitmap?>(initialValue = null, key1 = imageUrl) {
        value = loadGeneratedImage(imageUrl)
    }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .height(280.dp),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.62f),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.38f)),
            contentAlignment = Alignment.Center,
        ) {
            if (imageBitmap != null) {
                Image(
                    bitmap = imageBitmap!!,
                    contentDescription = title,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Fit,
                )
            } else {
                Text(
                    text = "图片已生成，正在加载预览",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private suspend fun loadGeneratedImage(imageUrl: String): ImageBitmap? {
    return loadGeneratedBitmap(imageUrl)?.asImageBitmap()
}

private suspend fun loadGeneratedBitmap(imageUrl: String): Bitmap? {
    val normalizedUrl = imageUrl.trim()
    if (normalizedUrl.isBlank()) {
        return null
    }
    return withContext(Dispatchers.IO) {
        runCatching {
            val connection = URL(normalizedUrl).openConnection().apply {
                connectTimeout = 3_000
                readTimeout = 6_000
            }
            connection.getInputStream().use { input ->
                BitmapFactory.decodeStream(input)
            }
        }.getOrNull()
    }
}

private suspend fun saveCheckinImageToGallery(
    context: Context,
    imageUrl: String,
    title: String,
): Boolean {
    val bitmap = loadGeneratedBitmap(imageUrl) ?: return false
    return withContext(Dispatchers.IO) {
        runCatching {
            val resolver = context.contentResolver
            val fileName = "short_drama_checkin_${System.currentTimeMillis()}.png"
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, fileName)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(MediaStore.Images.Media.TITLE, title)
                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/短剧打卡图")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: return@runCatching false
            resolver.openOutputStream(uri)?.use { output ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
            } ?: return@runCatching false
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
            true
        }.getOrDefault(false)
    }
}

private fun shareCheckinCard(
    context: Context,
    title: String,
    imageUrl: String,
    styleLabel: String,
) {
    val shareText = buildString {
        append(title)
        if (styleLabel.isNotBlank()) {
            append(" · ")
            append(styleLabel)
        }
        append("\n")
        append(imageUrl)
    }
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, shareText)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    runCatching {
        context.startActivity(Intent.createChooser(intent, "分享打卡图"))
    }
}


@Composable
private fun CheckinStyleSelector(
    selectedStyle: String,
    onStyleSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = "海报风格模板",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        CHECKIN_CARD_STYLE_OPTIONS.chunked(3).forEach { rowItems ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                rowItems.forEach { option ->
                    val selected = option.id == selectedStyle
                    Surface(
                        shape = RoundedCornerShape(999.dp),
                        color = if (selected) {
                            MaterialTheme.colorScheme.primaryContainer
                        } else {
                            MaterialTheme.colorScheme.surface.copy(alpha = 0.56f)
                        },
                        modifier = Modifier.clickable { onStyleSelected(option.id) },
                    ) {
                        Text(
                            text = option.label,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = if (selected) {
                                MaterialTheme.colorScheme.onPrimaryContainer
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                    }
                }
            }
        }
    }
}

private val CREATIVE_INTENT_PRESETS = listOf(
    "当场反击",
    "身份曝光",
    "甜宠和解",
    "反转黑化",
    "悬疑留钩子",
)
