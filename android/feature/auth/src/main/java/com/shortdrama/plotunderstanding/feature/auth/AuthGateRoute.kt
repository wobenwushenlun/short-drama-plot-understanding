package com.shortdrama.plotunderstanding.feature.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shortdrama.plotunderstanding.core.ui.AigcBackdrop
import com.shortdrama.plotunderstanding.core.ui.AigcModeToggle
import com.shortdrama.plotunderstanding.core.ui.AigcThemeMode

@Composable
fun AuthGateRoute(
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
    onAuthed: () -> Unit
) {
    Box(modifier = Modifier.fillMaxSize()) {
        AigcBackdrop()
        AigcModeToggle(
            themeMode = themeMode,
            onToggle = onToggleTheme,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(20.dp),
        )
        Card(
            modifier = Modifier
                .align(Alignment.Center)
                .padding(24.dp)
                .widthIn(max = 420.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(28.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text(
                    text = "AIGC SHORTPLAY",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "让剧情爽点\n成为可互动的瞬间",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = "基于视频证据生成互动节点、弹幕反馈与 AI 插片，进入后即可体验完整播放链路。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = onAuthed,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(text = "以游客身份进入")
                }
            }
        }
    }
}
