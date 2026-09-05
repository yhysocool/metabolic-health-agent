package com.healthevent.mobile.vivo;

import com.getcapacitor.JSObject;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TimeZone;
import java.util.UUID;

/** Builds the same stable vivo synchronization contract as the TypeScript client. */
final class VivoSyncPayloadBuilder {
    private static final Set<String> DAILY_ACTIVITY = new HashSet<>(Arrays.asList(
        "steps", "distance", "calories"
    ));
    private static final Set<String> SLEEP_METRICS = new HashSet<>(Arrays.asList(
        "sleep", "sleep_total_duration", "sleep_night_duration", "sleep_nap_duration",
        "sleep_light_duration", "sleep_deep_duration", "sleep_rem_duration",
        "sleep_awake_duration", "sleep_score", "sleep_deep_continuity",
        "sleep_awake_episode_count", "sleep_awake_episode_duration"
    ));
    private static final Set<String> SUPPORTED_METRICS = new HashSet<>();

    static {
        SUPPORTED_METRICS.addAll(DAILY_ACTIVITY);
        SUPPORTED_METRICS.addAll(SLEEP_METRICS);
        SUPPORTED_METRICS.addAll(Arrays.asList(
            "heart_rate", "heart_rate_resting", "spo2", "stress", "exercise"
        ));
    }

    static final class Result {
        final JSONObject payload;
        final long cursor;
        final int recordCount;
        final int collectionRunCount;
        final List<Long> observationIds;

        Result(JSONObject payload, long cursor, int recordCount, int collectionRunCount, List<Long> observationIds) {
            this.payload = payload;
            this.cursor = cursor;
            this.recordCount = recordCount;
            this.collectionRunCount = collectionRunCount;
            this.observationIds = observationIds;
        }
    }

    private static final class Times {
        final String identity;
        final long measuredAt;
        final long startTime;
        final Long endTime;

        Times(String identity, long measuredAt, long startTime, Long endTime) {
            this.identity = identity;
            this.measuredAt = measuredAt;
            this.startTime = startTime;
            this.endTime = endTime;
        }
    }

    private VivoSyncPayloadBuilder() {}

    static Result build(JSObject history, VivoAutoSyncStore.Config config) throws Exception {
        return build(history, new JSONArray(), config);
    }

    static Result build(JSObject history, JSONArray localObservations, VivoAutoSyncStore.Config config) throws Exception {
        JSONArray items = history.optJSONArray("items");
        LinkedHashMap<String, JSONObject> records = new LinkedHashMap<>();
        LinkedHashMap<String, JSONObject> collectionRuns = new LinkedHashMap<>();
        LinkedHashMap<String, Long> localObservationIds = new LinkedHashMap<>();
        long latestReadAt = config.cursor;

        if (items != null) {
            for (int index = 0; index < items.length(); index++) {
                JSONObject stored = items.optJSONObject(index);
                if (stored == null) continue;
                long storedReadAt = positiveLong(stored.opt("readAt"), System.currentTimeMillis());
                latestReadAt = Math.max(latestReadAt, storedReadAt);
                JSONObject snapshot = stored.optJSONObject("payload");
                if (snapshot == null) continue;
                long snapshotId = positiveLong(stored.opt("id"), 0L);
                if (snapshotId > 0L) {
                    String runId = "vivo-snapshot-" + snapshotId;
                    collectionRuns.putIfAbsent(runId, toCollectionRun(
                        runId,
                        stored.optString("status", "NO_DATA"),
                        snapshot,
                        storedReadAt
                    ));
                }
                JSONArray observations = snapshot.optJSONArray("observations");
                if (observations == null) continue;
                for (int observationIndex = 0; observationIndex < observations.length(); observationIndex++) {
                    JSONObject observation = observations.optJSONObject(observationIndex);
                    JSONObject record = toRecord(observation, snapshot, storedReadAt);
                    if (record != null) records.put(record.getString("record_id"), record);
                }
            }
        }

        if (localObservations != null) {
            for (int index = 0; index < localObservations.length(); index++) {
                JSONObject observation = localObservations.optJSONObject(index);
                if (observation == null) continue;
                long storedAt = positiveLong(observation.opt("syncedAt"), System.currentTimeMillis());
                JSONObject record = toRecord(observation, new JSONObject(), storedAt);
                if (record == null) continue;
                String recordId = record.getString("record_id");
                records.put(recordId, record);
                long localId = positiveLong(observation.opt("id"), 0L);
                if (localId > 0L) localObservationIds.put(recordId, localId);
            }
        }

        List<JSONObject> ordered = new ArrayList<>(records.values());
        int fromIndex = Math.max(0, ordered.size() - 1000);
        JSONArray bodyRecords = new JSONArray();
        List<Long> includedObservationIds = new ArrayList<>();
        for (int index = fromIndex; index < ordered.size(); index++) {
            JSONObject record = ordered.get(index);
            bodyRecords.put(record);
            Long localId = localObservationIds.get(record.optString("record_id", ""));
            if (localId != null) includedObservationIds.add(localId);
        }

        JSONObject payload = new JSONObject();
        payload.put("batch_id", UUID.randomUUID().toString());
        payload.put("user_id", config.userId);
        payload.put("device_id", config.deviceId);
        payload.put("cursor", latestReadAt > 0L ? String.valueOf(latestReadAt) : JSONObject.NULL);
        payload.put("records", bodyRecords);
        JSONArray bodyCollectionRuns = new JSONArray();
        for (JSONObject collectionRun : collectionRuns.values()) bodyCollectionRuns.put(collectionRun);
        payload.put("collection_runs", bodyCollectionRuns);
        return new Result(
            payload,
            latestReadAt,
            bodyRecords.length(),
            bodyCollectionRuns.length(),
            includedObservationIds
        );
    }

    private static JSONObject toCollectionRun(
        String runId,
        String status,
        JSONObject snapshot,
        long storedReadAt
    ) throws Exception {
        JSONArray observations = snapshot.optJSONArray("observations");
        int validRecordCount = 0;
        Long firstMeasuredAt = null;
        Long lastMeasuredAt = null;
        if (observations != null) {
            for (int index = 0; index < observations.length(); index++) {
                JSONObject observation = observations.optJSONObject(index);
                if (observation == null || !"PASS".equals(observation.optString("status"))) continue;
                if (finiteNumber(observation.opt("value")) == null) continue;
                validRecordCount++;
                Long measuredAt = positiveLongOrNull(observation.opt("measuredAt"));
                if (measuredAt != null) {
                    firstMeasuredAt = firstMeasuredAt == null ? measuredAt : Math.min(firstMeasuredAt, measuredAt);
                    lastMeasuredAt = lastMeasuredAt == null ? measuredAt : Math.max(lastMeasuredAt, measuredAt);
                }
            }
        }

        int providerRowCount = 0;
        JSONObject privateHealth = snapshot.optJSONObject("privateHealth");
        if (privateHealth != null) {
            JSONObject diagnostics = privateHealth.optJSONObject("providerDiagnostics");
            if (diagnostics != null) {
                providerRowCount += nonNegativeInt(diagnostics.opt("sleepRowCount"));
                providerRowCount += nonNegativeInt(diagnostics.opt("careRowCount"));
            }
            JSONObject vitals = privateHealth.optJSONObject("vitals");
            if (vitals != null) providerRowCount = Math.max(
                providerRowCount,
                nonNegativeInt(vitals.opt("careRowCount"))
            );
        }
        if (providerRowCount == 0 && validRecordCount > 0) providerRowCount = validRecordCount;

        JSONObject result = new JSONObject();
        result.put("run_id", runId);
        result.put("source", snapshot.optString("source", "vivo_phone"));
        result.put("read_at", isoUtc(storedReadAt));
        result.put("status", status == null || status.trim().isEmpty() ? "NO_DATA" : status);
        result.put("provider_row_count", providerRowCount);
        result.put("valid_record_count", validRecordCount);
        if (firstMeasuredAt != null) result.put("first_measured_at", isoUtc(firstMeasuredAt));
        if (lastMeasuredAt != null) result.put("last_measured_at", isoUtc(lastMeasuredAt));
        return result;
    }

    private static JSONObject toRecord(JSONObject observation, JSONObject snapshot, long storedReadAt) throws Exception {
        if (observation == null || !"PASS".equals(observation.optString("status"))) return null;
        String metric = observation.optString("metricType", "");
        if (!SUPPORTED_METRICS.contains(metric)) return null;
        Double value = finiteNumber(observation.opt("value"));
        if (value == null) return null;

        long fallback = positiveLong(snapshot.opt("readAtEpochMs"), storedReadAt);
        Times times = recordTimes(metric, observation, snapshot, fallback);
        String source = truncate(observation.optString("source", "vivo_local_health_provider"), 128);
        String sourceDevice = truncate(observation.optString("sourceDevice", "vivo_health_provider"), 128);
        String recordKey = source + "|" + sourceDevice + "|" + metric + "|" + times.identity;
        long syncedAt = positiveLong(observation.opt("syncedAt"), fallback);

        JSONObject record = new JSONObject();
        record.put("record_id", "vivo-" + sha256(recordKey));
        record.put("metric", metric);
        record.put("value", value);
        record.put("unit", truncate(observation.optString("unit", ""), 32));
        record.put("source", source);
        record.put("source_device", sourceDevice);
        record.put("measured_at", isoUtc(times.measuredAt));
        record.put("start_time", isoUtc(times.startTime));
        record.put("end_time", times.endTime == null ? JSONObject.NULL : isoUtc(times.endTime));
        record.put("status", "PASS");
        record.put("raw_source", truncate(observation.optString("rawSource", "vivo_bridge"), 256));
        record.put("synced_at", isoUtc(syncedAt));
        return record;
    }

    private static Times recordTimes(String metric, JSONObject observation, JSONObject snapshot, long fallback) {
        if (DAILY_ACTIVITY.contains(metric)) {
            JSONObject activity = snapshot.optJSONObject("activity");
            String day = activity == null ? "" : activity.optString("day", "");
            long start = parseLocalDay(day, fallback);
            return new Times(day.isEmpty() ? String.valueOf(start) : day, start, start, null);
        }
        if (SLEEP_METRICS.contains(metric)) {
            JSONObject privateHealth = snapshot.optJSONObject("privateHealth");
            JSONObject sleep = privateHealth == null ? null : privateHealth.optJSONObject("sleep");
            long sleepStart = sleep == null ? fallback : positiveLong(sleep.opt("sleepStartEpochMs"), fallback);
            long start = positiveLong(observation.opt("startTime"), sleepStart);
            Long end = positiveLongOrNull(observation.opt("endTime"));
            if (end == null && sleep != null) end = positiveLongOrNull(sleep.opt("sleepEndEpochMs"));
            String sourceDay = sleep == null ? "" : sleep.optString("sourceDay", "");
            long measuredAt = positiveLong(observation.opt("measuredAt"), start);
            return new Times(sourceDay.isEmpty() ? String.valueOf(start) : sourceDay, measuredAt, start, end);
        }
        long measuredAt = positiveLong(
            observation.has("measuredAt") ? observation.opt("measuredAt")
                : observation.has("startTime") ? observation.opt("startTime") : observation.opt("syncedAt"),
            fallback
        );
        long start = positiveLong(observation.opt("startTime"), measuredAt);
        return new Times(String.valueOf(measuredAt), measuredAt, start, positiveLongOrNull(observation.opt("endTime")));
    }

    private static long parseLocalDay(String day, long fallback) {
        if (day == null || !day.matches("\\d{4}-\\d{2}-\\d{2}")) return startOfLocalDay(fallback);
        try {
            SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            format.setLenient(false);
            Date parsed = format.parse(day);
            return parsed == null ? startOfLocalDay(fallback) : parsed.getTime();
        } catch (Exception ignored) {
            return startOfLocalDay(fallback);
        }
    }

    private static long startOfLocalDay(long epochMs) {
        Calendar calendar = Calendar.getInstance();
        calendar.setTimeInMillis(epochMs);
        calendar.set(Calendar.HOUR_OF_DAY, 0);
        calendar.set(Calendar.MINUTE, 0);
        calendar.set(Calendar.SECOND, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        return calendar.getTimeInMillis();
    }

    private static String isoUtc(long epochMs) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", Locale.US);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(epochMs));
    }

    private static long positiveLong(Object value, long fallback) {
        Long parsed = positiveLongOrNull(value);
        return parsed == null ? fallback : parsed;
    }

    private static Long positiveLongOrNull(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        try {
            long parsed = value instanceof Number ? ((Number) value).longValue() : Long.parseLong(String.valueOf(value));
            return parsed > 0L ? parsed : null;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static int nonNegativeInt(Object value) {
        Long parsed = positiveLongOrNull(value);
        return parsed == null ? 0 : (int) Math.min(Integer.MAX_VALUE, parsed);
    }

    private static Double finiteNumber(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        try {
            double parsed = value instanceof Number ? ((Number) value).doubleValue() : Double.parseDouble(String.valueOf(value));
            return Double.isFinite(parsed) ? parsed : null;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static String truncate(String value, int maxLength) {
        if (value == null) return "";
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    private static String sha256(String value) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte item : digest) result.append(String.format(Locale.US, "%02x", item));
        return result.toString();
    }
}
