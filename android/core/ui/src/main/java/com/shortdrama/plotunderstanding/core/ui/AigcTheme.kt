package com.shortdrama.plotunderstanding.core.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp

enum class AigcThemeMode {
    DAY,
    NIGHT;

    fun toggled(): AigcThemeMode = if (this == DAY) NIGHT else DAY
}

private val AigcDayColors = lightColorScheme(
    primary = Color(0xFF8A5900),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFFFE0A5),
    onPrimaryContainer = Color(0xFF2D1900),
    secondary = Color(0xFF006584),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFC3ECFF),
    onSecondaryContainer = Color(0xFF001F2A),
    tertiary = Color(0xFF65558F),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFE8DEFF),
    onTertiaryContainer = Color(0xFF201047),
    background = Color(0xFFFFFBF4),
    onBackground = Color(0xFF211A12),
    surface = Color(0xFFFFF9F0),
    onSurface = Color(0xFF211A12),
    surfaceVariant = Color(0xFFF4E8D6),
    onSurfaceVariant = Color(0xFF544736),
    error = Color(0xFFBA1A1A),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    outline = Color(0xFF857462),
    outlineVariant = Color(0xFFD8C7B3),
    scrim = Color(0xFF000000),
    inverseSurface = Color(0xFF362F26),
    inverseOnSurface = Color(0xFFFBEEE0),
    inversePrimary = Color(0xFFFFBA43),
)

private val AigcNightColors = darkColorScheme(
    primary = Color(0xFFF7C86C),
    onPrimary = Color(0xFF1D1608),
    primaryContainer = Color(0xFF3B2A09),
    onPrimaryContainer = Color(0xFFFFE9BC),
    secondary = Color(0xFF7DD3FC),
    onSecondary = Color(0xFF07141D),
    secondaryContainer = Color(0xFF0F273A),
    onSecondaryContainer = Color(0xFFD5F3FF),
    tertiary = Color(0xFFB8A0FF),
    onTertiary = Color(0xFF16102B),
    tertiaryContainer = Color(0xFF2A2048),
    onTertiaryContainer = Color(0xFFE9E0FF),
    background = Color(0xFF070B14),
    onBackground = Color(0xFFE7ECF5),
    surface = Color(0xFF0C1322),
    onSurface = Color(0xFFE7ECF5),
    surfaceVariant = Color(0xFF18233A),
    onSurfaceVariant = Color(0xFFC4D0E2),
    error = Color(0xFFFFB4A9),
    onError = Color(0xFF5F150F),
    errorContainer = Color(0xFF8C1C18),
    onErrorContainer = Color(0xFFFFDAD6),
    outline = Color(0xFF5E6A83),
    outlineVariant = Color(0xFF364056),
    scrim = Color(0xFF000000),
    inverseSurface = Color(0xFFE7ECF5),
    inverseOnSurface = Color(0xFF121826),
    inversePrimary = Color(0xFF645400),
)

private val AigcShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(36.dp),
)

private val BaseTypography = Typography()
private val AigcTypography = BaseTypography.copy(
    headlineLarge = BaseTypography.headlineLarge.copy(fontWeight = FontWeight.SemiBold),
    headlineMedium = BaseTypography.headlineMedium.copy(fontWeight = FontWeight.SemiBold),
    headlineSmall = BaseTypography.headlineSmall.copy(fontWeight = FontWeight.SemiBold),
    titleLarge = BaseTypography.titleLarge.copy(fontWeight = FontWeight.SemiBold),
    titleMedium = BaseTypography.titleMedium.copy(fontWeight = FontWeight.Medium),
    titleSmall = BaseTypography.titleSmall.copy(fontWeight = FontWeight.Medium),
    labelLarge = BaseTypography.labelLarge.copy(fontWeight = FontWeight.Medium),
)

@Composable
fun AigcTheme(
    themeMode: AigcThemeMode = AigcThemeMode.NIGHT,
    content: @Composable () -> Unit
) {
    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
        MaterialTheme(
            colorScheme = if (themeMode == AigcThemeMode.DAY) AigcDayColors else AigcNightColors,
            typography = AigcTypography,
            shapes = AigcShapes,
            content = content
        )
    }
}
