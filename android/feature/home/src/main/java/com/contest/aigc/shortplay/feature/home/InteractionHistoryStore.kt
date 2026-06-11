package com.contest.aigc.shortplay.feature.home

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

data class InteractionLocalRecord(
    val recordId: String,
    val dramaId: String,
    val episodeId: String,
    val nodeId: String,
    val nodeTitle: String,
    val optionId: String,
    val optionText: String,
    val feedbackText: String,
    val nextActionType: String,
    val branchSegmentId: String?,
    val recordedAtMs: Long,
)

object InteractionHistoryStore {
    private const val FILE_NAME = "interaction_records.json"
    private const val MAX_RECORDS = 20

    suspend fun load(context: Context): List<InteractionLocalRecord> {
        return withContext(Dispatchers.IO) {
            val file = historyFile(context)
            if (!file.exists()) {
                return@withContext emptyList()
            }
            runCatching {
                file.bufferedReader(Charsets.UTF_8).use { reader ->
                    JSONArray(reader.readText()).toRecords()
                }
            }.getOrElse {
                emptyList()
            }
        }
    }

    suspend fun append(context: Context, record: InteractionLocalRecord) {
        withContext(Dispatchers.IO) {
            val file = historyFile(context)
            val records = if (file.exists()) {
                runCatching {
                    file.bufferedReader(Charsets.UTF_8).use { reader ->
                        JSONArray(reader.readText()).toRecords()
                    }
                }.getOrElse { emptyList() }
            } else {
                emptyList()
            }
            val updated = (listOf(record) + records).take(MAX_RECORDS)
            file.parentFile?.mkdirs()
            file.bufferedWriter(Charsets.UTF_8).use { writer ->
                writer.write(updated.toJsonArray().toString())
            }
        }
    }

    private fun historyFile(context: Context): File {
        return File(context.filesDir, FILE_NAME)
    }
}

private fun JSONArray.toRecords(): List<InteractionLocalRecord> {
    val result = mutableListOf<InteractionLocalRecord>()
    for (index in 0 until length()) {
        val item = getJSONObject(index)
        result += InteractionLocalRecord(
            recordId = item.optString("recordId"),
            dramaId = item.optString("dramaId"),
            episodeId = item.optString("episodeId"),
            nodeId = item.optString("nodeId"),
            nodeTitle = item.optString("nodeTitle"),
            optionId = item.optString("optionId"),
            optionText = item.optString("optionText"),
            feedbackText = item.optString("feedbackText"),
            nextActionType = item.optString("nextActionType"),
            branchSegmentId = item.optString("branchSegmentId").takeIf { it.isNotBlank() },
            recordedAtMs = item.optLong("recordedAtMs"),
        )
    }
    return result
}

private fun List<InteractionLocalRecord>.toJsonArray(): JSONArray {
    val array = JSONArray()
    for (record in this) {
        array.put(record.toJson())
    }
    return array
}

private fun InteractionLocalRecord.toJson(): JSONObject {
    return JSONObject()
        .put("recordId", recordId)
        .put("dramaId", dramaId)
        .put("episodeId", episodeId)
        .put("nodeId", nodeId)
        .put("nodeTitle", nodeTitle)
        .put("optionId", optionId)
        .put("optionText", optionText)
        .put("feedbackText", feedbackText)
        .put("nextActionType", nextActionType)
        .put("branchSegmentId", branchSegmentId)
        .put("recordedAtMs", recordedAtMs)
}
