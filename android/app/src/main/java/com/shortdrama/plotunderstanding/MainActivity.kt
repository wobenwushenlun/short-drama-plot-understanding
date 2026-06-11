package com.shortdrama.plotunderstanding

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.shortdrama.plotunderstanding.core.ui.AigcTheme
import com.shortdrama.plotunderstanding.core.ui.AigcThemeMode
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.view.WindowCompat

private const val THEME_PREFERENCES = "aigc_ui_preferences"
private const val THEME_MODE_KEY = "theme_mode"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        val preferences = getSharedPreferences(THEME_PREFERENCES, MODE_PRIVATE)
        val initialThemeMode = readThemeMode(preferences.getString(THEME_MODE_KEY, null))
        setTheme(
            if (initialThemeMode == AigcThemeMode.DAY) {
                R.style.Theme_AigcAndroid_Day
            } else {
                R.style.Theme_AigcAndroid_Night
            }
        )
        super.onCreate(savedInstanceState)
        setContent {
            var themeModeName by rememberSaveable { mutableStateOf(initialThemeMode.name) }
            val themeMode = readThemeMode(themeModeName)
            SideEffect {
                val dayMode = themeMode == AigcThemeMode.DAY
                window.statusBarColor = getColor(
                    if (dayMode) R.color.aigc_day_background else R.color.aigc_night_background
                )
                window.navigationBarColor = getColor(
                    if (dayMode) R.color.aigc_day_background else R.color.aigc_night_background
                )
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = dayMode
                    isAppearanceLightNavigationBars = dayMode
                }
            }
            AigcTheme(themeMode = themeMode) {
                AppNavHost(
                    themeMode = themeMode,
                    onToggleTheme = {
                        val nextThemeMode = themeMode.toggled()
                        themeModeName = nextThemeMode.name
                        preferences.edit().putString(THEME_MODE_KEY, nextThemeMode.name).apply()
                    }
                )
            }
        }
    }
}

private fun readThemeMode(value: String?): AigcThemeMode {
    return if (value == AigcThemeMode.DAY.name) AigcThemeMode.DAY else AigcThemeMode.NIGHT
}
