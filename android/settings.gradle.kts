pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven {
            url = uri("local_maven")
        }
        google()
        mavenCentral()
    }
}

rootProject.name = "aigc-android"

include(":app")
include(":core:ui")
include(":feature:auth")
include(":feature:home")
