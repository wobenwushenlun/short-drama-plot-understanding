package com.shortdrama.plotunderstanding.feature.home

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable

internal enum class PlayerAigcOverlaySmokeEntry {
    STORY_CONTINUATION,
    CHECKIN_CARD,
}

internal val playerAigcOverlaySmokeEntries = PlayerAigcOverlaySmokeEntry.entries

internal val playerAigcGeneratedAssetSmoke = GeneratedMediaAsset(
    assetId = "checkin_card_smoke.png",
    remoteUrl = "https://cdn.example.test/checkin.png",
    localUrl = "http://127.0.0.1:8000/media/generated-assets/checkin_card_smoke.png",
    mediaUrl = "http://127.0.0.1:8000/media/generated-assets/checkin_card_smoke.png",
    contentType = "image/png",
    cacheStatus = "cached",
    byteSize = 1024L,
    degradeReason = "",
)

@Composable
internal fun PlayerAigcOverlaySmokeSurface(entry: PlayerAigcOverlaySmokeEntry) {
    MaterialTheme {
        when (entry) {
            PlayerAigcOverlaySmokeEntry.STORY_CONTINUATION -> StoryContinuationOverlay(
                state = null,
                userIntent = "",
                onUserIntentChange = {},
                onGenerate = {},
                onPlay = {},
                onGenerateCheckin = {},
                onDismiss = {},
            )

            PlayerAigcOverlaySmokeEntry.CHECKIN_CARD -> CheckinCardOverlay(
                state = null,
                selectedStyle = "family_glory",
                userIntent = "",
                onUserIntentChange = {},
                onStyleSelected = {},
                onGenerate = {},
                onDismiss = {},
            )
        }
    }
}
