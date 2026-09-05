package com.healthevent.mobile.vivo;

import android.content.Context;

import com.getcapacitor.JSObject;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;

import javax.net.ssl.HttpsURLConnection;

/** HTTPS client used only by the Android background job. */
final class VivoAutoSyncClient {
    private static final int MAX_REQUEST_BYTES = 2 * 1024 * 1024;
    private static final int MAX_RESPONSE_BYTES = 64 * 1024;

    private VivoAutoSyncClient() {}

    static JSObject enroll(Context context, String rawBaseUrl, String enrollmentCode) throws Exception {
        String code = enrollmentCode == null ? "" : enrollmentCode.trim();
        if (code.length() < 16) {
            throw new IllegalArgumentException("绑定码无效");
        }
        String baseUrl = VivoAutoSyncStore.normalizeHttpsBaseUrl(rawBaseUrl);
        String deviceId = VivoDeviceIdentityStore.deviceId(context);
        JSONObject request = new JSONObject();
        request.put("enrollment_code", code);
        request.put("device_id", deviceId);
        request.put("public_key", VivoDeviceIdentityStore.publicKey(context));
        request.put("proof", VivoDeviceIdentityStore.signEnrollment(context, code));
        byte[] body = request.toString().getBytes(StandardCharsets.UTF_8);

        URL endpoint = new URL(baseUrl + "/api/integrations/vivo/devices/enroll");
        HttpsURLConnection connection = (HttpsURLConnection) endpoint.openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(15_000);
            connection.setReadTimeout(30_000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }

            int statusCode = connection.getResponseCode();
            InputStream responseStream = statusCode >= 200 && statusCode < 300
                ? connection.getInputStream() : connection.getErrorStream();
            String responseBody = readLimited(responseStream);
            if (statusCode < 200 || statusCode >= 300) {
                String detail = "HTTP " + statusCode;
                try {
                    detail += "：" + new JSONObject(responseBody).optString("detail", "服务器拒绝设备绑定");
                } catch (Exception ignored) {
                    // Keep the status-only error; never expose an unbounded server response.
                }
                throw new IllegalStateException(detail);
            }

            JSONObject response = new JSONObject(responseBody);
            String syncToken = response.optString("sync_token", "").trim();
            String userId = response.optString("user_id", "").trim();
            String enrolledDeviceId = response.optString("device_id", deviceId).trim();
            if (syncToken.length() < 32 || userId.isEmpty() || !deviceId.equals(enrolledDeviceId)) {
                throw new IllegalStateException("服务器返回的设备绑定结果不完整");
            }

            VivoAutoSyncStore store = new VivoAutoSyncStore(context);
            store.configureProvisioned(baseUrl, syncToken, userId, null, deviceId);
            store.recordConfigured("设备绑定成功；已启用自动采集和自动上传");
            return store.publicStatus();
        } finally {
            connection.disconnect();
        }
    }

    static JSObject syncNow(Context context, boolean captureFreshSnapshot) {
        VivoAutoSyncStore configStore = new VivoAutoSyncStore(context);
        configStore.recordAttempt();
        try {
            VivoAutoSyncStore.Config config = configStore.load();
            if (!config.enabled || config.baseUrl.isEmpty() || config.token.length() < 32) {
                throw new IllegalStateException("后台同步尚未配置");
            }

            VivoHealthSnapshotStore snapshotStore = new VivoHealthSnapshotStore(context);
            VivoOvernightStore observationStore = new VivoOvernightStore(context);
            try {
                if (captureFreshSnapshot) {
                    JSObject snapshot = VivoHealthSnapshotReader.read(context);
                    snapshotStore.saveIfChanged(snapshot);
                    String sessionId = context
                        .getSharedPreferences("vivo_overnight_capture", Context.MODE_PRIVATE)
                        .getString("sessionId", "auto-sync");
                    VivoOvernightCaptureService.persistSnapshotObservations(
                        observationStore,
                        snapshot,
                        sessionId == null || sessionId.trim().isEmpty() ? "auto-sync" : sessionId
                    );
                }
                JSObject history = snapshotStore.readAfter(config.cursor, 1000);
                if (!"PASS".equals(history.optString("status"))) {
                    throw new IllegalStateException(history.optString("message", "读取待同步快照失败"));
                }
                VivoSyncPayloadBuilder.Result payload = VivoSyncPayloadBuilder.build(
                    history,
                    observationStore.readPending(1000),
                    config
                );
                if (payload.recordCount == 0 && payload.collectionRunCount == 0) {
                    String message = "没有新的健康记录或采集运行记录需要上传";
                    configStore.recordSuccess(payload.cursor, 0, 0, 0, message);
                    return configStore.publicStatus();
                }
                return upload(configStore, config, payload, observationStore);
            } finally {
                observationStore.close();
                snapshotStore.close();
            }
        } catch (Exception exception) {
            String message = "后台同步失败：" + safeMessage(exception);
            configStore.recordError(message);
            return configStore.publicStatus();
        }
    }

    static boolean shouldRun(Context context) {
        VivoAutoSyncStore store = new VivoAutoSyncStore(context);
        try {
            VivoAutoSyncStore.Config config = store.load();
            return config.enabled && System.currentTimeMillis() - store.lastAttemptAt() >= VivoAutoSyncStore.MIN_SYNC_INTERVAL_MS;
        } catch (Exception exception) {
            store.recordError("后台同步配置不可用：" + safeMessage(exception));
            return false;
        }
    }

    private static JSObject upload(
        VivoAutoSyncStore store,
        VivoAutoSyncStore.Config config,
        VivoSyncPayloadBuilder.Result payload,
        VivoOvernightStore observationStore
    ) throws Exception {
        byte[] body = payload.payload.toString().getBytes(StandardCharsets.UTF_8);
        if (body.length > MAX_REQUEST_BYTES) {
            throw new IllegalStateException("待同步数据超过 2MB，请缩短同步间隔后重试");
        }

        URL endpoint = new URL(config.baseUrl + "/api/integrations/vivo/sync");
        HttpsURLConnection connection = (HttpsURLConnection) endpoint.openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(15_000);
            connection.setReadTimeout(30_000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + config.token);
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }

            int statusCode = connection.getResponseCode();
            InputStream responseStream = statusCode >= 200 && statusCode < 300
                ? connection.getInputStream() : connection.getErrorStream();
            String responseBody = readLimited(responseStream);
            if (statusCode < 200 || statusCode >= 300) {
                String detail = "HTTP " + statusCode;
                try {
                    detail += "：" + new JSONObject(responseBody).optString("detail", "服务器拒绝同步");
                } catch (Exception ignored) {
                    // Keep the status-only error; never expose an unbounded server response.
                }
                throw new IllegalStateException(detail);
            }

            JSONObject response = new JSONObject(responseBody);
            int created = response.optInt("created", 0);
            int updated = response.optInt("updated", 0);
            int unchanged = response.optInt("unchanged", 0);
            int uploadedObservations = observationStore.markUploaded(payload.observationIds);
            String message = "自动同步成功：新增 " + created + "，更新 " + updated + "，重复 " + unchanged
                + "；本地观察记录已确认 " + uploadedObservations + " 条";
            store.recordSuccess(payload.cursor, created, updated, unchanged, message);
            return store.publicStatus();
        } finally {
            connection.disconnect();
        }
    }

    private static String readLimited(InputStream stream) throws Exception {
        if (stream == null) return "";
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > MAX_RESPONSE_BYTES) throw new IllegalStateException("服务器响应过大");
                output.write(buffer, 0, read);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static String safeMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty() ? exception.getClass().getSimpleName() : message;
    }
}
