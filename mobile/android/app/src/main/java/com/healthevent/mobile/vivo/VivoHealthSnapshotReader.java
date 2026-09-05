package com.healthevent.mobile.vivo;

import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;

import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Unified read-only snapshot of the verified Akari Pulse vivo data sources.
 * This is an adapter for HengKang, not a replacement for the existing AI/API layers.
 */
public final class VivoHealthSnapshotReader {
    private static final String STEP_PERMISSION = "com.vivo.assistant.StepProvider";
    private static final String STEP_SETTINGS = "vivo_settings_realtime_steps";
    private static final Uri STEP_URI = Uri.parse("content://com.vivo.assistant.step.provider");
    private static final String SLEEP_AUTHORITY = "com.vivo.health.provider";
    private static final String CARE_AUTHORITY = "com.vivo.health.provider.care";
    private static final Uri SLEEP_URI = Uri.parse("content://" + SLEEP_AUTHORITY + "/sleep");
    private static final Uri CARE_URI = Uri.parse("content://" + CARE_AUTHORITY + "/healthCare");
    private static final String PRIVATE_PERMISSION = VivoPrivateHealthReader.PERMISSION;

    private VivoHealthSnapshotReader() {}

    public static JSObject read(Context context) {
        long readAt = System.currentTimeMillis();
        ZoneId zone = ZoneId.systemDefault();
        JSObject result = new JSObject();
        result.put("source", "vivo_phone");
        result.put("readAtEpochMs", readAt);
        result.put("readAt", isoTime(readAt, zone));
        result.put("timezone", zone.getId());
        JSObject activity = readActivity(context, readAt, zone);
        JSObject privateHealth = readPrivateHealth(context, readAt, zone);
        result.put("activity", activity);
        result.put("privateHealth", privateHealth);
        result.put("observations", buildObservations(activity, privateHealth, readAt));
        return result;
    }

    private static JSObject readActivity(Context context, long readAt, ZoneId zone) {
        JSObject result = new JSObject();
        result.put("source", "vivo_assistant_step_provider");
        result.put("day", java.time.LocalDate.ofInstant(Instant.ofEpochMilli(readAt), zone).toString());
        result.put("timezone", zone.getId());
        result.put("sampleEpochMs", readAt);
        result.put("sampledAt", isoTime(readAt, zone));
        result.put("sourceTimestampAvailable", false);
        result.put("settingsRealtimeStepsRaw", Settings.System.getString(context.getContentResolver(), STEP_SETTINGS));

        if (ContextCompat.checkSelfPermission(context, STEP_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            return activityStatus(result, VivoSpO2Reading.DENIED, "未授予 vivo 步数 Provider 权限", true);
        }

        try {
            Bundle capability = context.getContentResolver().call(STEP_URI, "canJoviStep", null, null);
            if (capability == null) {
                return activityStatus(result, VivoSpO2Reading.UNSUPPORTED, "vivo 步数 Provider 没有返回能力结果", true);
            }
            Integer canStep = numberAsInt(capability.get("can_step"));
            if (canStep == null || canStep != 1) {
                return activityStatus(result, VivoSpO2Reading.NO_DATA, "设备当前没有可用步数数据", true);
            }
            result.put("capabilityFields", bundleToJson(capability));

            Bundle extras = new Bundle();
            extras.putBoolean("ignore", true);
            Bundle provider = context.getContentResolver().call(STEP_URI, "updateTodaySportAIDLBean", null, extras);
            if (provider == null) {
                return activityStatus(result, VivoSpO2Reading.NO_DATA, "vivo 步数 Provider 当前没有数据", true);
            }
            Number steps = number(provider.get("step"));
            Number distance = number(provider.get("distance"));
            Number calories = number(provider.get("calorie"));
            if (steps == null || distance == null || calories == null ||
                steps.doubleValue() < 0d || distance.doubleValue() < 0d || calories.doubleValue() < 0d) {
                return activityStatus(result, VivoSpO2Reading.ERROR, "vivo 步数 Provider 返回字段不完整或非法", true);
            }
            result.put("status", VivoSpO2Reading.PASS);
            result.put("outcome", "PROVIDER_CALL_SUCCEEDED");
            result.put("message", "已读取今日活动数据");
            result.put("steps", steps.intValue());
            result.put("distanceMeters", distance.doubleValue());
            result.put("caloriesKilocalories", calories.doubleValue());
            result.put("providerKeys", sortedKeys(provider));
            result.put("providerFields", bundleToJson(provider));
            return result;
        } catch (SecurityException exception) {
            return activityStatus(result, VivoSpO2Reading.DENIED, "vivo 步数 Provider 拒绝访问", true);
        } catch (IllegalArgumentException exception) {
            return activityStatus(result, VivoSpO2Reading.UNSUPPORTED, "设备不存在 vivo 步数 Provider", true);
        } catch (Exception exception) {
            return activityStatus(result, VivoSpO2Reading.ERROR, "读取活动数据失败：" + exception.getClass().getSimpleName(), true);
        }
    }

    private static JSObject readPrivateHealth(Context context, long readAt, ZoneId zone) {
        JSObject result = new JSObject();
        boolean permissionGranted = ContextCompat.checkSelfPermission(context, PRIVATE_PERMISSION) == PackageManager.PERMISSION_GRANTED;
        boolean providersResolved = context.getPackageManager().resolveContentProvider(SLEEP_AUTHORITY, 0) != null &&
            context.getPackageManager().resolveContentProvider(CARE_AUTHORITY, 0) != null;
        result.put("permissionGranted", permissionGranted);
        result.put("providersResolved", providersResolved);
        result.put("readAtEpochMs", readAt);
        result.put("readAt", isoTime(readAt, zone));

        if (!providersResolved) {
            result.put("capability", "UNSUPPORTED");
            result.put("status", VivoSpO2Reading.UNSUPPORTED);
            result.put("message", "设备不存在 vivo 私有健康 Provider");
            result.put("sleep", unavailableMetric(VivoSpO2Reading.UNSUPPORTED, "Provider 不存在"));
            result.put("vitals", unavailableVitals(VivoSpO2Reading.UNSUPPORTED, "Provider 不存在"));
            return result;
        }
        if (!permissionGranted) {
            result.put("capability", "NOT_GRANTED");
            result.put("status", VivoSpO2Reading.DENIED);
            result.put("message", "未授予 vivo 私有健康 Provider 权限");
            result.put("sleep", unavailableMetric(VivoSpO2Reading.DENIED, "未授予权限"));
            result.put("vitals", unavailableVitals(VivoSpO2Reading.DENIED, "未授予权限"));
            return result;
        }

        try {
            List<Map<String, String>> sleepRows = allRows(context, SLEEP_URI);
            Map<String, String> sleepRow = latestSleepRow(sleepRows);
            List<Map<String, String>> careRows = allRows(context, CARE_URI);
            Map<String, String> careRow = latestCareRow(careRows);
            result.put("providerDiagnostics", providerDiagnostics(sleepRows, sleepRow, careRow, careRows.size()));
            JSObject sleep = parseSleep(sleepRow, zone);
            result.put("sleepHistory", parseSleepHistory(sleepRows, zone));
            JSObject vitals = parseVitals(careRows, zone);
            boolean anyPass = VivoSpO2Reading.PASS.equals(sleep.optString("status")) ||
                VivoSpO2Reading.PASS.equals(vitals.optString("status"));
            result.put("capability", "GRANTED");
            result.put("status", anyPass ? VivoSpO2Reading.PASS : VivoSpO2Reading.NO_DATA);
            result.put("message", anyPass ? "已读取 vivo 睡眠和最新生命体征" : "Provider 当前没有睡眠或生命体征数据");
            result.put("sleep", sleep);
            result.put("vitals", vitals);
            return result;
        } catch (SecurityException exception) {
            result.put("capability", "NOT_GRANTED");
            result.put("status", VivoSpO2Reading.DENIED);
            result.put("message", "vivo 私有健康 Provider 拒绝访问");
            result.put("sleep", unavailableMetric(VivoSpO2Reading.DENIED, "Provider 拒绝访问"));
            result.put("vitals", unavailableVitals(VivoSpO2Reading.DENIED, "Provider 拒绝访问"));
            return result;
        } catch (IllegalArgumentException exception) {
            result.put("capability", "UNSUPPORTED");
            result.put("status", VivoSpO2Reading.UNSUPPORTED);
            result.put("message", "设备不存在可用的 vivo 私有健康 Provider");
            result.put("sleep", unavailableMetric(VivoSpO2Reading.UNSUPPORTED, "Provider 不存在"));
            result.put("vitals", unavailableVitals(VivoSpO2Reading.UNSUPPORTED, "Provider 不存在"));
            return result;
        } catch (Exception exception) {
            result.put("capability", "ERROR");
            result.put("status", VivoSpO2Reading.ERROR);
            result.put("message", "读取 vivo 私有健康数据失败：" + exception.getClass().getSimpleName());
            result.put("sleep", unavailableMetric(VivoSpO2Reading.ERROR, "读取异常"));
            result.put("vitals", unavailableVitals(VivoSpO2Reading.ERROR, "读取异常"));
            return result;
        }
    }

    private static JSObject parseSleep(Map<String, String> row, ZoneId zone) {
        if (row == null) return unavailableMetric(VivoSpO2Reading.NO_DATA, "Provider 当前没有睡眠数据");
        try {
            String sourceDay = required(row, "DATE");
            long sourceDayStart = requiredLong(row, "TIMESTAMP");
            long sleepStart = requiredLong(row, "ENTER_TIME");
            long sleepEnd = requiredLong(row, "EXIT_TIME");
            long total = requiredLong(row, "TOTAL_DURATION");
            if (sleepEnd <= sleepStart || total < 0L) throw new IllegalArgumentException("睡眠时间范围非法");

            JSObject result = new JSObject();
            result.put("status", VivoSpO2Reading.PASS);
            result.put("outcome", "PROVIDER_CALL_SUCCEEDED");
            result.put("sourceDay", sourceDay);
            result.put("sourceDayStartEpochMs", sourceDayStart);
            result.put("sleepStartEpochMs", sleepStart);
            result.put("sleepEndEpochMs", sleepEnd);
            result.put("totalDurationMs", total);
            putOptionalLong(result, "nightSleepDurationMs", optionalNonNegativeLong(row, "NIGHT_SLEEP_TOTAL"));
            putOptionalLong(result, "napDurationMs", optionalNonNegativeLong(row, "NAP_TOTAL"));
            putOptionalLong(result, "chartTotalDurationMs", optionalNonNegativeLong(row, "CHARVIEW_TOTAL_DURATION"));
            putOptionalLong(result, "lightSleepDurationMs", optionalNonNegativeLong(row, "LIGHT_SLEEP_DURATION"));
            putOptionalLong(result, "deepSleepDurationMs", optionalNonNegativeLong(row, "DEEP_SLEEP_DURATION"));
            putOptionalLong(result, "remSleepDurationMs", optionalNonNegativeLong(row, "REM_SLEEP_DURATION"));
            putOptionalLong(result, "awakeDurationMs", optionalNonNegativeLong(row, "AWAKE_SLEEP_DURATION"));
            putOptionalInt(result, "score", optionalInt(row, "SCORE"));
            putOptionalInt(result, "deepSleepContinuity", optionalInt(row, "DEEP_SLEEP_CONTINUITY"));
            putOptionalInt(result, "recorderGeneration", optionalInt(row, "WATCH_GENERATION"));
            Integer lowAccuracy = optionalInt(row, "SLEEP_LOW_ACCURACY");
            if (lowAccuracy != null) result.put("lowAccuracy", lowAccuracy != 0);
            WakeSummary wake = parseInteriorAwake(row.get("AWAKE_SLEEP_LIST"), sleepStart, sleepEnd);
            result.put("awakeEpisodeCount", wake.count);
            result.put("awakeEpisodeDurationMs", wake.durationMs);
            result.put("timezone", zone.getId());
            result.put("providerColumns", new JSONArray(sortedKeys(row)));
            result.put("rawFields", mapToJson(row));
            return result;
        } catch (Exception exception) {
            return unavailableMetric(VivoSpO2Reading.ERROR, "睡眠 Provider Schema 解析失败：" + exception.getMessage());
        }
    }

    private static JSONArray parseSleepHistory(List<Map<String, String>> rows, ZoneId zone) {
        JSONArray result = new JSONArray();
        if (rows == null) return result;
        for (Map<String, String> row : rows) {
            JSObject parsed = parseSleep(row, zone);
            parsed.remove("rawFields");
            result.put(parsed);
        }
        return result;
    }

    private static JSObject parseVitals(List<Map<String, String>> rows, ZoneId zone) throws JSONException {
        if (rows == null || rows.isEmpty()) return unavailableVitals(VivoSpO2Reading.NO_DATA, "Provider 当前没有生命体征数据");
        JSObject result = new JSObject();
        java.util.Set<String> columns = new java.util.HashSet<>();
        JSObject heart = null;
        JSObject spo2 = null;
        JSObject stress = null;
        JSONArray heartHistory = new JSONArray();
        JSONArray spo2History = new JSONArray();
        JSONArray stressHistory = new JSONArray();
        Map<String, String> latestRow = null;
        JSONObject latestData = null;
        long latestAnyTimestamp = -1L;
        for (Map<String, String> row : rows) {
            columns.addAll(row.keySet());
            String raw = row.get(VivoPrivateHealthReader.MYSELF_DATA);
            if (raw == null || raw.trim().isEmpty()) continue;
            JSONObject data = VivoPrivateHealthReader.firstObject(new JSONObject(raw));
            JSObject candidateHeart = parseVital(data, "heartValue", "heartTimeStamp", "heartAbnormalType", "bpm", zone);
            JSObject candidateSpo2 = parseVital(data, "saO2Value", "saO2TimeStamp", "oxygenAbnormal", "%", zone);
            JSObject candidateStress = parseVital(data, "pressureValue", "pressureTimeStamp", "pressAbnormal", "score", zone);
            appendHistory(heartHistory, candidateHeart);
            appendHistory(spo2History, candidateSpo2);
            appendHistory(stressHistory, candidateStress);
            heart = newestVital(heart, candidateHeart);
            spo2 = newestVital(spo2, candidateSpo2);
            stress = newestVital(stress, candidateStress);
            long candidateTimestamp = newestTimestamp(candidateHeart, candidateSpo2, candidateStress);
            if (latestRow == null || candidateTimestamp > latestAnyTimestamp) {
                latestRow = row;
                latestData = data;
                latestAnyTimestamp = candidateTimestamp;
            }
        }
        if (heart == null) heart = unavailableVital("bpm", VivoSpO2Reading.NO_DATA, "Provider 当前没有心率数据");
        if (spo2 == null) spo2 = unavailableVital("%", VivoSpO2Reading.NO_DATA, "Provider 当前没有血氧数据");
        if (stress == null) stress = unavailableVital("score", VivoSpO2Reading.NO_DATA, "Provider 当前没有压力数据");
        java.util.List<String> columnList = new ArrayList<>(columns);
        java.util.Collections.sort(columnList);
        result.put("providerColumns", new JSONArray(columnList));
        result.put("careRowCount", rows.size());
        result.put("heartRateHistory", heartHistory);
        result.put("spo2History", spo2History);
        result.put("stressHistory", stressHistory);
        result.put("spo2HistoryCount", spo2History.length());
        result.put("spo2AccessMode", spo2History.length() > 1 ? "PROVIDER_ROWS" : "LATEST_SINGLE_POINT");
        result.put("spo2CoverageMessage", spo2History.length() > 1
            ? "Provider 返回了多条带源时间的血氧记录，已全部保留"
            : "当前 Provider 只暴露一个有效血氧单点，不能代表 vivo 健康内部的完整夜间序列");
        if (latestRow != null) result.put("rawFields", mapToJson(latestRow));
        if (latestData != null) result.put("rawData", latestData);
        result.put("status", VivoSpO2Reading.PASS.equals(heart.optString("status")) ||
            VivoSpO2Reading.PASS.equals(spo2.optString("status")) ||
            VivoSpO2Reading.PASS.equals(stress.optString("status")) ? VivoSpO2Reading.PASS : VivoSpO2Reading.NO_DATA);
        result.put("outcome", "PROVIDER_CALL_SUCCEEDED");
        result.put("providerSourceFrom", latestData == null ? null : latestData.optString("sourceFrom", null));
        result.put("heartRate", heart);
        result.put("spo2", spo2);
        result.put("stress", stress);
        return result;
    }

    private static JSObject parseVital(JSONObject data, String valueKey, String timestampKey, String abnormalKey, String unit, ZoneId zone) {
        JSObject result = new JSObject();
        result.put("unit", unit);
        if (!data.has(valueKey) || !data.has(timestampKey)) {
            result.put("status", VivoSpO2Reading.UNSUPPORTED);
            result.put("outcome", "SCHEMA_UNSUPPORTED");
            result.put("message", "Provider Schema 缺少 " + valueKey + " 或 " + timestampKey);
            return result;
        }
        Double value = jsonDouble(data.opt(valueKey));
        Long timestamp = VivoPrivateHealthReader.parseTimestamp(data.opt(timestampKey));
        Integer abnormal = jsonInt(data.opt(abnormalKey));
        if (value == null || timestamp == null || value <= 0d || timestamp <= 0L) {
            result.put("status", VivoSpO2Reading.NO_DATA);
            result.put("outcome", "PROVIDER_NO_DATA");
            if (abnormal != null) result.put("abnormalFlag", abnormal);
            return result;
        }
        result.put("status", VivoSpO2Reading.PASS);
        result.put("outcome", "PROVIDER_CALL_SUCCEEDED");
        result.put("value", value);
        result.put("sourceEpochMs", timestamp);
        result.put("sourceTime", isoTime(timestamp, zone));
        if (abnormal != null) result.put("abnormalFlag", abnormal);
        return result;
    }

    private static List<Map<String, String>> allRows(Context context, Uri uri) {
        List<Map<String, String>> rows = new ArrayList<>();
        try (Cursor cursor = context.getContentResolver().query(uri, null, null, null, null)) {
            if (cursor == null) return rows;
            while (cursor.moveToNext()) {
                Map<String, String> row = new LinkedHashMap<>();
                for (String column : cursor.getColumnNames()) {
                    row.put(column, cursor.getString(cursor.getColumnIndexOrThrow(column)));
                }
                rows.add(row);
            }
        }
        return rows;
    }

    private static Map<String, String> latestSleepRow(List<Map<String, String>> rows) {
        Map<String, String> latest = null;
        long latestStart = -1L;
        if (rows == null) return null;
        for (Map<String, String> row : rows) {
            try {
                long start = requiredLong(row, "ENTER_TIME");
                if (latest == null || start > latestStart) {
                    latest = row;
                    latestStart = start;
                }
            } catch (Exception ignored) {
                if (latest == null) latest = row;
            }
        }
        return latest;
    }

    private static Map<String, String> latestCareRow(List<Map<String, String>> rows) {
        Map<String, String> latest = null;
        long latestTimestamp = -1L;
        if (rows == null) return null;
        for (Map<String, String> row : rows) {
            String raw = row.get(VivoPrivateHealthReader.MYSELF_DATA);
            if (raw == null || raw.trim().isEmpty()) continue;
            try {
                JSONObject data = VivoPrivateHealthReader.firstObject(new JSONObject(raw));
                Long timestamp = VivoPrivateHealthReader.parseTimestamp(data.opt("saO2TimeStamp"));
                if (latest == null || (timestamp != null && timestamp > latestTimestamp)) {
                    latest = row;
                    latestTimestamp = timestamp == null ? latestTimestamp : timestamp;
                }
            } catch (JSONException ignored) {
                // parseVitals reports the schema error; row selection remains best effort.
            }
        }
        return latest;
    }

    private static JSObject providerDiagnostics(
        List<Map<String, String>> sleepRows,
        Map<String, String> sleepRow,
        Map<String, String> careRow,
        int careRowCount
    ) {
        JSObject result = new JSObject();
        result.put("sleepAuthority", SLEEP_AUTHORITY);
        result.put("sleepPath", SLEEP_URI.getPath());
        result.put("sleepRowPresent", sleepRow != null);
        result.put("sleepRowCount", sleepRows == null ? 0 : sleepRows.size());
        result.put("sleepColumns", new JSONArray(sleepRow == null ? new ArrayList<String>() : sortedKeys(sleepRow)));
        result.put("careAuthority", CARE_AUTHORITY);
        result.put("carePath", CARE_URI.getPath());
        result.put("careRowPresent", careRow != null);
        result.put("careRowCount", careRowCount);
        result.put("careColumns", new JSONArray(careRow == null ? new ArrayList<String>() : sortedKeys(careRow)));
        return result;
    }

    private static JSONArray buildObservations(JSObject activity, JSObject privateHealth, long readAt) {
        JSONArray result = new JSONArray();
        appendObjectObservation(result, "steps", "step", activity, "steps", readAt, null, null,
            "vivo_assistant_step_provider");
        appendObjectObservation(result, "distance", "m", activity, "distanceMeters", readAt, null, null,
            "vivo_assistant_step_provider");
        appendObjectObservation(result, "calories", "kcal", activity, "caloriesKilocalories", readAt, null, null,
            "vivo_assistant_step_provider");

        JSONArray sleepHistory = privateHealth.optJSONArray("sleepHistory");
        if (sleepHistory != null && sleepHistory.length() > 0) {
            for (int index = 0; index < sleepHistory.length(); index++) {
                appendSleepObservations(result, sleepHistory.optJSONObject(index));
            }
        } else {
            appendSleepObservations(result, privateHealth.optJSONObject("sleep"));
        }

        JSONObject vitals = privateHealth.optJSONObject("vitals");
        if (vitals != null) {
            appendVitalObservation(result, "heart_rate", vitals.optJSONObject("heartRate"), "bpm");
            appendVitalObservation(result, "spo2", vitals.optJSONObject("spo2"), "%");
            appendVitalObservation(result, "stress", vitals.optJSONObject("stress"), "score");
        }
        return result;
    }

    private static void appendSleepObservations(JSONArray result, JSONObject sleep) {
        if (sleep != null) {
            Long sleepStart = numberAsLong(sleep.opt("sleepStartEpochMs"));
            Long sleepEnd = numberAsLong(sleep.opt("sleepEndEpochMs"));
            appendObjectObservation(result, "sleep_total_duration", "ms", sleep, "totalDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_night_duration", "ms", sleep, "nightSleepDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_nap_duration", "ms", sleep, "napDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_light_duration", "ms", sleep, "lightSleepDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_deep_duration", "ms", sleep, "deepSleepDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_rem_duration", "ms", sleep, "remSleepDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_awake_duration", "ms", sleep, "awakeDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_score", "score", sleep, "score", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_deep_continuity", "score", sleep, "deepSleepContinuity", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_awake_episode_count", "count", sleep, "awakeEpisodeCount", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
            appendObjectObservation(result, "sleep_awake_episode_duration", "ms", sleep, "awakeEpisodeDurationMs", sleepEnd,
                sleepStart, sleepEnd, "vivo_health_provider/sleep");
        }

    }

    private static void appendVitalObservation(JSONArray target, String metric, JSONObject vital, String unit) {
        if (vital == null) {
            appendObservation(target, metric, unit, VivoSpO2Reading.UNSUPPORTED, null, null, null, null,
                "vivo_health_provider.care/healthCare:MYSELF_DATA");
            return;
        }
        Long measuredAt = numberAsLong(vital.opt("sourceEpochMs"));
        Object value = vital.opt("value");
        String status = vital.optString("status", VivoSpO2Reading.NO_DATA);
        appendObservation(target, metric, unit, status, value, measuredAt, measuredAt, measuredAt,
            "vivo_health_provider.care/healthCare:MYSELF_DATA");
    }

    private static void appendHistory(JSONArray target, JSObject vital) throws JSONException {
        if (vital == null || !VivoSpO2Reading.PASS.equals(vital.optString("status"))) return;
        Long timestamp = numberAsLong(vital.opt("sourceEpochMs"));
        Object value = vital.opt("value");
        if (timestamp == null || timestamp <= 0L || value == null || JSONObject.NULL.equals(value)) return;
        String dedupeKey = timestamp + ":" + String.valueOf(value);
        for (int index = 0; index < target.length(); index++) {
            JSONObject existing = target.optJSONObject(index);
            if (existing != null && dedupeKey.equals(existing.optString("_dedupeKey"))) return;
        }
        JSONObject entry = new JSONObject(vital.toString());
        entry.put("_dedupeKey", dedupeKey);
        target.put(entry);
    }

    private static JSObject newestVital(JSObject current, JSObject candidate) {
        if (candidate == null || !VivoSpO2Reading.PASS.equals(candidate.optString("status"))) return current;
        if (current == null || !VivoSpO2Reading.PASS.equals(current.optString("status"))) return candidate;
        Long candidateTimestamp = numberAsLong(candidate.opt("sourceEpochMs"));
        Long currentTimestamp = numberAsLong(current.opt("sourceEpochMs"));
        if (candidateTimestamp != null && (currentTimestamp == null || candidateTimestamp > currentTimestamp)) return candidate;
        return current;
    }

    private static long newestTimestamp(JSObject... vitals) {
        long latest = -1L;
        for (JSObject vital : vitals) {
            if (vital == null || !VivoSpO2Reading.PASS.equals(vital.optString("status"))) continue;
            Long timestamp = numberAsLong(vital.opt("sourceEpochMs"));
            if (timestamp != null && timestamp > latest) latest = timestamp;
        }
        return latest;
    }

    private static void appendObjectObservation(
        JSONArray target,
        String metric,
        String unit,
        JSONObject source,
        String valueKey,
        Long measuredAt,
        Long startTime,
        Long endTime,
        String rawSource
    ) {
        Object value = source == null ? null : source.opt(valueKey);
        String status = source == null ? VivoSpO2Reading.UNSUPPORTED : source.optString("status", VivoSpO2Reading.NO_DATA);
        if (value == null || JSONObject.NULL.equals(value)) {
            if (VivoSpO2Reading.PASS.equals(status)) status = VivoSpO2Reading.UNSUPPORTED;
            value = null;
        }
        appendObservation(target, metric, unit, status, value, measuredAt, startTime, endTime, rawSource);
    }

    private static void appendObservation(
        JSONArray target,
        String metric,
        String unit,
        String status,
        Object value,
        Long measuredAt,
        Long startTime,
        Long endTime,
        String rawSource
    ) {
        JSObject observation = new JSObject();
       observation.put("metricType", metric);
       observation.put("source", "vivo_local_health_provider");
       observation.put("sourceDevice", "vivo_watch_gt");
       observation.put("status", status);
       if (value != null && !JSONObject.NULL.equals(value)) observation.put("value", value);
       if (measuredAt != null && measuredAt > 0L) observation.put("measuredAt", measuredAt);
       if (startTime != null && startTime > 0L) observation.put("startTime", startTime);
       if (endTime != null && endTime > 0L) observation.put("endTime", endTime);
       observation.put("unit", unit);
       observation.put("rawSource", rawSource);
       observation.put("syncedAt", System.currentTimeMillis());
       target.put(observation);
   }

    private static JSObject activityStatus(JSObject result, String status, String message, boolean includeDiagnostics) {
        result.put("status", status);
        result.put("outcome", status.equals(VivoSpO2Reading.PASS) ? "PROVIDER_CALL_SUCCEEDED" : "PROVIDER_NO_DATA");
        result.put("message", message);
        if (includeDiagnostics) {
            result.put("steps", null);
            result.put("distanceMeters", null);
            result.put("caloriesKilocalories", null);
        }
        return result;
    }

    private static JSObject unavailableMetric(String status, String message) {
        JSObject result = new JSObject();
        result.put("status", status);
        result.put("outcome", status.equals(VivoSpO2Reading.NO_DATA) ? "PROVIDER_NO_DATA" : "PROVIDER_CALL_FAILED");
        result.put("message", message);
        return result;
    }

    private static JSObject unavailableVitals(String status, String message) {
        JSObject result = new JSObject();
        result.put("status", status);
        result.put("outcome", status.equals(VivoSpO2Reading.NO_DATA) ? "PROVIDER_NO_DATA" : "PROVIDER_CALL_FAILED");
        result.put("message", message);
        result.put("heartRate", unavailableVital("bpm", status, message));
        result.put("spo2", unavailableVital("%", status, message));
        result.put("stress", unavailableVital("score", status, message));
        return result;
    }

    private static JSObject unavailableVital(String unit, String status, String message) {
        JSObject result = new JSObject();
        result.put("status", status);
        result.put("outcome", "PROVIDER_NO_DATA");
        result.put("unit", unit);
        result.put("message", message);
        return result;
    }

    private static WakeSummary parseInteriorAwake(String raw, long sleepStart, long sleepEnd) throws JSONException {
        if (raw == null || raw.trim().isEmpty()) return new WakeSummary(null, null);
        JSONArray items = new JSONArray(raw);
        int count = 0;
        long duration = 0L;
        for (int index = 0; index < items.length(); index++) {
            JSONObject item = items.optJSONObject(index);
            if (item == null) throw new JSONException("AWAKE_SLEEP_LIST 不是对象数组");
            long enter = item.optLong("enterTime", -1L);
            long exit = item.optLong("exitTime", -1L);
            if (enter <= 0L || exit < enter) throw new JSONException("AWAKE_SLEEP_LIST 时间非法");
            if (enter > sleepStart && exit < sleepEnd) {
                count++;
                duration += exit - enter;
            }
        }
        return new WakeSummary(count, duration);
    }

    private static String required(Map<String, String> row, String key) {
        String value = row.get(key);
        if (value == null || value.trim().isEmpty()) throw new IllegalArgumentException("缺少 " + key);
        return value;
    }

    private static long requiredLong(Map<String, String> row, String key) {
        try { return Long.parseLong(required(row, key)); }
        catch (NumberFormatException exception) { throw new IllegalArgumentException(key + " 不是整数"); }
    }

    private static Long optionalNonNegativeLong(Map<String, String> row, String key) {
        String raw = row.get(key);
        if (raw == null || raw.trim().isEmpty()) return null;
        try {
            long value = Long.parseLong(raw);
            if (value < 0L) throw new IllegalArgumentException(key + " 不能为负数");
            return value;
        } catch (NumberFormatException exception) { throw new IllegalArgumentException(key + " 不是整数"); }
    }

    private static Integer optionalInt(Map<String, String> row, String key) {
        String raw = row.get(key);
        if (raw == null || raw.trim().isEmpty()) return null;
        try { return Integer.parseInt(raw); }
        catch (NumberFormatException exception) { throw new IllegalArgumentException(key + " 不是整数"); }
    }

    private static Number number(Object value) {
        if (value instanceof Number) return (Number) value;
        if (value == null) return null;
        try { return Double.parseDouble(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static Integer numberAsInt(Object value) {
        Number number = number(value);
        return number == null ? null : number.intValue();
    }

    private static Double jsonDouble(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        try { return Double.parseDouble(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static Long jsonLong(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        try { return Long.parseLong(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static Integer jsonInt(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        try { return Integer.parseInt(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static List<String> sortedKeys(Bundle bundle) {
        List<String> keys = new ArrayList<>(bundle.keySet());
        java.util.Collections.sort(keys);
        return keys;
    }

    private static List<String> sortedKeys(Map<String, String> row) {
        List<String> keys = new ArrayList<>(row.keySet());
        java.util.Collections.sort(keys);
        return keys;
    }

    private static JSONObject mapToJson(Map<String, String> row) throws JSONException {
        JSONObject result = new JSONObject();
        for (Map.Entry<String, String> entry : row.entrySet()) result.put(entry.getKey(), entry.getValue());
        return result;
    }

    private static JSONObject bundleToJson(Bundle bundle) throws JSONException {
        JSONObject result = new JSONObject();
        for (String key : bundle.keySet()) {
            Object value = bundle.get(key);
            if (value == null) continue;
            if (value instanceof Number || value instanceof Boolean || value instanceof String) {
                result.put(key, value);
            } else {
                result.put(key, String.valueOf(value));
            }
        }
        return result;
    }

    private static Long numberAsLong(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        if (value instanceof Number) return ((Number) value).longValue();
        try { return Long.parseLong(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static void putOptionalLong(JSObject object, String key, Long value) { if (value != null) object.put(key, value); }
    private static void putOptionalInt(JSObject object, String key, Integer value) { if (value != null) object.put(key, value); }
    private static String isoTime(long epochMs, ZoneId zone) { return Instant.ofEpochMilli(epochMs).atZone(zone).toOffsetDateTime().toString(); }

    private static final class WakeSummary {
        final Integer count;
        final Long durationMs;
        WakeSummary(Integer count, Long durationMs) { this.count = count; this.durationMs = durationMs; }
    }
}
