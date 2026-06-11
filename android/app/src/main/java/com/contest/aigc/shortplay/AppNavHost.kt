package com.contest.aigc.shortplay

import com.contest.aigc.shortplay.feature.home.AiExperienceRoute
import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.contest.aigc.shortplay.feature.auth.AuthGateRoute
import com.contest.aigc.shortplay.feature.home.DramaDetailRoute
import com.contest.aigc.shortplay.feature.home.HomeRoute
import com.contest.aigc.shortplay.feature.home.PlayerRoute
import com.contest.aigc.shortplay.feature.home.WatchHistoryRoute
import com.contest.aigc.shortplay.core.ui.AigcThemeMode

private const val PLAYER_ROUTE = "player/{episodeId}?startMs={startMs}"

@Composable
fun AppNavHost(
    themeMode: AigcThemeMode,
    onToggleTheme: () -> Unit,
) {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = "auth"
    ) {
        composable("auth") {
            AuthGateRoute(
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onAuthed = {
                    navController.navigate("home") {
                        popUpTo("auth") { inclusive = true }
                    }
                }
            )
        }

        composable("home") {
            HomeRoute(
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onOpenHistory = {
                    navController.navigate("history")
                },
                onOpenAi = {
                    navController.navigate("ai")
                },
                onOpenDrama = { dramaId ->
                    navController.navigate("detail/$dramaId")
                },
                onOpenEpisode = { episodeId, startMs ->
                    navController.navigate("player/$episodeId?startMs=$startMs")
                }
            )
        }

        composable("ai") {
            AiExperienceRoute(
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onBack = {
                    navController.backToHomeOrPop()
                },
                onOpenEpisode = { episodeId, startMs ->
                    navController.navigate("player/$episodeId?startMs=$startMs")
                }
            )
        }

        composable("history") {
            WatchHistoryRoute(
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onBack = {
                    navController.backToHomeOrPop()
                },
                onOpenEpisode = { episodeId, startMs ->
                    navController.navigate("player/$episodeId?startMs=$startMs")
                }
            )
        }

        composable(
            route = "detail/{dramaId}",
            arguments = listOf(navArgument("dramaId") { type = NavType.StringType })
        ) { backStackEntry ->
            val dramaId = backStackEntry.arguments?.getString("dramaId").orEmpty()
            DramaDetailRoute(
                dramaId = dramaId,
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onPlayEpisode = { episodeId, startMs ->
                    navController.navigate("player/$episodeId?startMs=$startMs")
                },
                onBack = {
                    navController.backToHomeOrPop()
                }
            )
        }

        composable(
            route = PLAYER_ROUTE,
            arguments = listOf(
                navArgument("episodeId") { type = NavType.StringType },
                navArgument("startMs") {
                    type = NavType.LongType
                    defaultValue = 0L
                }
            )
        ) { backStackEntry ->
            val episodeId = backStackEntry.arguments?.getString("episodeId").orEmpty()
            val startMs = backStackEntry.arguments?.getLong("startMs") ?: 0L
            PlayerRoute(
                episodeId = episodeId,
                initialPositionMs = startMs,
                themeMode = themeMode,
                onToggleTheme = onToggleTheme,
                onPlayEpisode = { nextEpisodeId, nextStartMs ->
                    navController.navigate("player/$nextEpisodeId?startMs=$nextStartMs") {
                        popUpTo(PLAYER_ROUTE) {
                            inclusive = true
                        }
                    }
                },
                onBack = {
                    navController.backToDetailOrHome(episodeId)
                }
            )
        }
    }
}

private fun NavHostController.backToHomeOrPop() {
    if (!popBackStack("home", false)) {
        navigate("home") {
            launchSingleTop = true
        }
    }
}

private fun NavHostController.backToDetailOrHome(episodeId: String) {
    val dramaId = episodeId.substringBeforeLast("_ep", missingDelimiterValue = "tainai3")
    val detailRoute = "detail/$dramaId"
    if (!popBackStack(detailRoute, false)) {
        navigate(detailRoute) {
            launchSingleTop = true
        }
    }
}
