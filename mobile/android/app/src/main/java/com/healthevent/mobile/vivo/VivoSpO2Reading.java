package com.healthevent.mobile.vivo;

import com.getcapacitor.JSObject;

/**
 * One observation returned by the vivo local care Provider.
 *
 * <p>This object deliberately represents a single source observation. It must
 * not be expanded into a continuous series when the Provider returns the same
 * source timestamp.</p>
 */
public final class VivoSpO2Reading {
    public static final String PASS = "PASS";
    public static final String NO_DATA = "NO_DATA";
    public static final String DENIED = "DENIED";
    public static final String UNSUPPORTED = "UNSUPPORTED";
    public static final String ERROR = "ERROR";

    public final String status;
    public final String message;
    public final double value;
    public final long measuredAt;
    public final String rawSource;

    private VivoSpO2Reading(String status, String message, double value, long measuredAt, String rawSource) {
        this.status = status;
        this.message = message;
        this.value = value;
        this.measuredAt = measuredAt;
        this.rawSource = rawSource;
    }

    public static VivoSpO2Reading pass(double value, long measuredAt, String rawSource) {
        return new VivoSpO2Reading(PASS, "已读取一个最新血氧观测点", value, measuredAt, rawSource);
    }

    public static VivoSpO2Reading ofStatus(String status, String message, String rawSource) {
        return new VivoSpO2Reading(status, message, 0d, 0L, rawSource);
    }

    public JSObject toJson() {
        JSObject result = new JSObject();
        result.put("status", status);
        result.put("message", message);
        result.put("source", "vivo_local_health_provider");
        result.put("sourceDevice", "vivo_health_provider");
        result.put("metricType", "spo2");
        result.put("measuredAt", measuredAt > 0 ? measuredAt : null);
        result.put("startTime", measuredAt > 0 ? measuredAt : null);
        result.put("endTime", measuredAt > 0 ? measuredAt : null);
        result.put("value", status.equals(PASS) ? value : null);
        result.put("unit", "%");
        result.put("rawSource", rawSource);
        result.put("syncedAt", System.currentTimeMillis());
        return result;
    }
}
