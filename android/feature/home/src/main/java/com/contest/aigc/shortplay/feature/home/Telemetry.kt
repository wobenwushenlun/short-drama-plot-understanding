package com.contest.aigc.shortplay.feature.home

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

object AnalyticsOutboxStore {
    private const val FILE_NAME = "analytics_outbox.json"
    private const val MAX_RECORDS = 100

    suspend fun load(context: Context): List<TelemetryEvent> {
        return withContext(Dispatchers.IO) {
            val file = historyFile(context)
            if (!file.exists()) {
                return@withContext emptyList()
            }
            runCatching {
                file.bufferedReader(Charsets.UTF_8).use { reader ->
                    JSONArray(reader.readText()).toTelemetryEvents()
                }
            }.getOrElse {
                emptyList()
            }
        }
    }

    suspend fun append(context: Context, events: List<TelemetryEvent>) {
        withContext(Dispatchers.IO) {
            val file = historyFile(context)
            val existing = if (file.exists()) {
                runCatching {
                    file.bufferedReader(Charsets.UTF_8).use { reader ->
                        JSONArray(reader.readText()).toTelemetryEvents()
                    }
                }.getOrElse { emptyList() }
            } else {
                emptyList()
            }
            val updated = (events + existing).take(MAX_RECORDS)
            file.parentFile?.mkdirs()
            file.bufferedWriter(Charsets.UTF_8).use { writer ->
                writer.write(updated.toJsonArray().toString())
            }
        }
    }

    suspend fun clear(context: Context) {
        withContext(Dispatchers.IO) {
            historyFile(context).takeIf { it.exists() }?.delete()
        }
    }

    private fun historyFile(context: Context): File {
        return File(context.filesDir, FILE_NAME)
    }
}

class BackendTelemetryDispatcher(
    private val repository: ShortPlayRepository,
) {
    suspend fun track(context: Context, events: List<TelemetryEvent>) {
        val queued = AnalyticsOutboxStore.load(context)
        val merged = if (queued.isEmpty()) events else queued + events
        if (merged.isEmpty()) {
            return
        }

        try {
            repository.reportTelemetryEvents(merged)
            AnalyticsOutboxStore.clear(context)
        } catch (throwable: Throwable) {
            AnalyticsOutboxStore.append(context, events)
        }
    }
}

private fun JSONArray.toTelemetryEvents(): List<TelemetryEvent> {
    val result = mutableListOf<TelemetryEvent>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += TelemetryEvent(
            eventId = item.optString("eventId"),
            eventName = item.optString("eventName"),
            screenName = item.optString("screenName"),
            dramaId = item.optString("dramaId").takeIf { it.isNotBlank() },
            episodeId = item.optString("episodeId").takeIf { it.isNotBlank() },
            nodeId = item.optString("nodeId").takeIf { it.isNotBlank() },
            progressMs = if (item.has("progressMs") && !item.isNull("progressMs")) item.optLong("progressMs") else null,
            clientTsMs = item.optLong("clientTsMs"),
            properties = item.optJSONObject("properties").toStringMap(),
        )
    }
    return result
}

private fun List<TelemetryEvent>.toJsonArray(): JSONArray {
    val array = JSONArray()
    for (event in this) {
        array.put(event.toJson())
    }
    return array
}

private fun TelemetryEvent.toJson(): JSONObject {
    return JSONObject()
        .put("eventId", eventId)
        .put("eventName", eventName)
        .put("screenName", screenName)
        .put("dramaId", dramaId)
        .put("episodeId", episodeId)
        .put("nodeId", nodeId)
        .put("progressMs", progressMs)
        .put("clientTsMs", clientTsMs)
        .put("properties", JSONObject(properties))
}

private fun JSONObject?.toStringMap(): Map<String, String> {
    if (this == null) {
        return emptyMap()
    }
    val result = linkedMapOf<String, String>()
    val iterator = keys()
    while (iterator.hasNext()) {
        val key = iterator.next()
        result[key] = optString(key)
    }
    return result
}
