package com.healthevent.mobile.vivo;

import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;

import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Minimal, read-only adapter for the vivo local care Provider.
 *
 * <p>The Provider currently exposes the latest care row. This reader therefore
 * returns one observation and leaves series construction to the capture layer,
 * which only persists advancing source timestamps.</p>
 */
public final class VivoPrivateHealthReader {
    public static final String PERMISSION = "com.vivo.health.widget.permission";
    public static final String AUTHORITY = "com.vivo.health.provider.care";
    public static final Uri CARE_URI = Uri.parse("content://" + AUTHORITY + "/healthCare");
    static final String MYSELF_DATA = "MYSELF_DATA";
    static final String VALUE_FIELD = "saO2Value";
    static final String TIMESTAMP_FIELD = "saO2TimeStamp";
    private static final String RAW_SOURCE = "vivo_health_provider.care/healthCare:MYSELF_DATA.saO2Value";

    private VivoPrivateHealthReader() {}

    public static VivoSpO2Reading probe(Context context) {
        if (ContextCompat.checkSelfPermission(context, PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.DENIED,
                "未授予 vivo 私有健康 Provider 权限",
                RAW_SOURCE
            );
        }

        try (Cursor cursor = context.getContentResolver().query(CARE_URI, null, null, null, null)) {
            if (cursor == null) {
                return VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.UNSUPPORTED,
                    "vivo 健康 Provider 未返回可用游标",
                    RAW_SOURCE
                );
            }
            if (cursor.getColumnCount() == 0) {
                return VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.UNSUPPORTED,
                    "vivo 健康 Provider 没有可识别字段",
                    RAW_SOURCE
                );
            }
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.PASS,
                "vivo 私有健康 Provider 可访问",
                RAW_SOURCE
            );
        } catch (SecurityException exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.DENIED,
                "vivo 健康 Provider 拒绝访问",
                RAW_SOURCE
            );
        } catch (IllegalArgumentException exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.UNSUPPORTED,
                "设备不存在 vivo 健康 Provider",
                RAW_SOURCE
            );
        } catch (Exception exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.ERROR,
                "探测 vivo 健康 Provider 失败：" + exception.getClass().getSimpleName(),
                RAW_SOURCE
            );
        }
    }

    public static VivoSpO2Reading readLatestSpO2(Context context) {
        VivoSpO2Reading capability = probe(context);
        if (!VivoSpO2Reading.PASS.equals(capability.status)) {
            return capability;
        }

        try {
            JSONObject data = latestCareData(context);
            if (data == null) {
                return VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.NO_DATA,
                    "Provider 当前没有血氧数据",
                    RAW_SOURCE
                );
            }
            if (!data.has(VALUE_FIELD) || !data.has(TIMESTAMP_FIELD)) {
                return VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.UNSUPPORTED,
                    "Provider Schema 缺少 saO2Value 或 saO2TimeStamp",
                    RAW_SOURCE
                );
            }

            Double value = parseDouble(data.opt(VALUE_FIELD));
            Long timestamp = parseTimestamp(data.opt(TIMESTAMP_FIELD));
            if (value == null || value <= 0d || timestamp == null || timestamp <= 0L) {
                return VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.NO_DATA,
                    "Provider 当前没有带有效时间戳的血氧数据",
                    RAW_SOURCE
                );
            }
            return VivoSpO2Reading.pass(value, timestamp, RAW_SOURCE);
        } catch (SecurityException exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.DENIED,
                "vivo 健康 Provider 拒绝访问",
                RAW_SOURCE
            );
        } catch (IllegalArgumentException exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.UNSUPPORTED,
                "设备不存在 vivo 健康 Provider",
                RAW_SOURCE
            );
        } catch (JSONException exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.UNSUPPORTED,
                "Provider 返回的 MYSELF_DATA 不是可识别 JSON",
                RAW_SOURCE
            );
        } catch (Exception exception) {
            return VivoSpO2Reading.ofStatus(
                VivoSpO2Reading.ERROR,
                "读取血氧失败：" + exception.getClass().getSimpleName(),
                RAW_SOURCE
            );
        }
    }

    static String readColumn(Cursor cursor, String expectedName) {
        String[] names = cursor.getColumnNames();
        for (int index = 0; index < names.length; index++) {
            if (expectedName.equalsIgnoreCase(names[index])) {
                return cursor.getString(index);
            }
        }
        return null;
    }

    static JSONObject firstObject(JSONObject object) throws JSONException {
        if (object.has(MYSELF_DATA) && object.opt(MYSELF_DATA) instanceof JSONObject) {
            return object.getJSONObject(MYSELF_DATA);
        }
        return object;
    }

    static Double parseDouble(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) {
            return null;
        }
        try {
            return Double.parseDouble(String.valueOf(value).trim());
        } catch (NumberFormatException exception) {
            return null;
        }
    }

    static Long parseTimestamp(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) {
            return null;
        }
        String text = String.valueOf(value).trim();
        try {
            double number = Double.parseDouble(text);
            long rounded = Math.round(number);
            if (rounded < 1_000_000_000L) {
                return null;
            }
            if (rounded < 100_000_000_000L) {
                return rounded * 1000L;
            }
            return rounded;
        } catch (NumberFormatException ignored) {
            String[] patterns = {"yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss"};
            for (String pattern : patterns) {
                try {
                    Date parsed = new SimpleDateFormat(pattern, Locale.US).parse(text);
                    return parsed == null ? null : parsed.getTime();
                } catch (ParseException ignoredPattern) {
                    // Try the next known provider representation.
                }
            }
            return null;
        }
    }

    /**
     * The care Provider may return more than one row, but does not promise
     * cursor ordering. Select by the Provider measurement timestamp instead
     * of trusting the first row.
     */
    static JSONObject latestCareData(Context context) throws Exception {
        JSONObject latest = null;
        long latestTimestamp = -1L;
        try (Cursor cursor = context.getContentResolver().query(CARE_URI, null, null, null, null)) {
            if (cursor == null) return null;
            while (cursor.moveToNext()) {
                String myselfData = readColumn(cursor, MYSELF_DATA);
                if (myselfData == null || myselfData.trim().isEmpty()) continue;
                JSONObject data = firstObject(new JSONObject(myselfData));
                Long timestamp = parseTimestamp(data.opt(TIMESTAMP_FIELD));
                if (latest == null || (timestamp != null && timestamp > latestTimestamp)) {
                    latest = data;
                    latestTimestamp = timestamp == null ? latestTimestamp : timestamp;
                }
            }
        }
        return latest;
    }
}
