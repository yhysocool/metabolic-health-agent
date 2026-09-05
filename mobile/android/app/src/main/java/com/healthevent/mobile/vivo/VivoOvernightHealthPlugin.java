package com.healthevent.mobile.vivo;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Capacitor bridge for the user-controlled overnight SpO2 experiment. */
@CapacitorPlugin(name = "VivoOvernightHealth")
public final class VivoOvernightHealthPlugin extends Plugin {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @PluginMethod
    public void probe(PluginCall call) {
        executor.execute(() -> call.resolve(VivoPrivateHealthReader.probe(getContext()).toJson()));
    }

    @PluginMethod
    public void readSpO2Once(PluginCall call) {
        executor.execute(() -> call.resolve(VivoPrivateHealthReader.readLatestSpO2(getContext()).toJson()));
    }

    @PluginMethod
    public void readSnapshot(PluginCall call) {
        executor.execute(() -> {
            JSObject snapshot = VivoHealthSnapshotReader.read(getContext());
            VivoHealthSnapshotStore store = new VivoHealthSnapshotStore(getContext());
            snapshot.put("persistence", store.saveIfChanged(snapshot));
            store.close();
            call.resolve(snapshot);
        });
    }

    @PluginMethod
    public void startSession(PluginCall call) {
        int intervalSeconds = call.getInt("intervalSeconds", 60);
        executor.execute(() -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                ContextCompat.checkSelfPermission(getContext(), Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                getActivity().runOnUiThread(() -> ActivityCompat.requestPermissions(
                    getActivity(),
                    new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    2402
                ));
                call.resolve(VivoSpO2Reading.ofStatus(
                    VivoSpO2Reading.DENIED,
                    "请允许通知权限后再次开始夜间采集",
                    "android.permission.POST_NOTIFICATIONS"
                ).toJson());
                return;
            }
            VivoSpO2Reading capability = VivoPrivateHealthReader.probe(getContext());
            if (VivoSpO2Reading.DENIED.equals(capability.status) || VivoSpO2Reading.UNSUPPORTED.equals(capability.status)) {
                call.resolve(capability.toJson());
                return;
            }
            String sessionId = call.getString("sessionId", UUID.randomUUID().toString());
            VivoOvernightCaptureService.start(getContext(), intervalSeconds, sessionId);
            call.resolve(getStatusJson(sessionId));
        });
    }

    @PluginMethod
    public void stopSession(PluginCall call) {
        VivoOvernightCaptureService.stop(getContext());
        call.resolve(getStatusJson(null));
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        executor.execute(() -> call.resolve(getStatusJson(null)));
    }

    @PluginMethod
    public void getSessionSamples(PluginCall call) {
        executor.execute(() -> {
            String sessionId = call.getString("sessionId");
            if (sessionId == null || sessionId.trim().isEmpty()) {
                call.reject("sessionId 不能为空", "INVALID_ARGUMENT");
                return;
            }
            VivoOvernightStore store = new VivoOvernightStore(getContext());
            JSArray samples = store.readSession(sessionId);
            store.close();
            JSObject result = new JSObject();
            result.put("sessionId", sessionId);
            result.put("items", samples);
            call.resolve(result);
        });
    }

    @PluginMethod
    public void getHealthHistory(PluginCall call) {
        executor.execute(() -> {
            int limit = call.getInt("limit", 30);
            VivoHealthSnapshotStore store = new VivoHealthSnapshotStore(getContext());
            JSObject result = store.readRecent(limit);
            store.close();
            VivoOvernightStore observationStore = new VivoOvernightStore(getContext());
            result.put("observations", observationStore.readAll(limit));
            observationStore.close();
            call.resolve(result);
        });
    }

    @PluginMethod
    public void configureAutoSync(PluginCall call) {
        executor.execute(() -> {
            try {
                VivoAutoSyncStore store = new VivoAutoSyncStore(getContext());
                store.configure(
                    call.getString("baseUrl"),
                    call.getString("token"),
                    call.getString("userId"),
                    call.getString("cursor")
                );
                if (!VivoAutoSyncJobService.schedule(getContext())) {
                    store.recordError("系统拒绝注册后台同步任务");
                    call.reject("系统拒绝注册后台同步任务", "SCHEDULE_FAILED");
                    return;
                }
                VivoAutoSyncJobService.scheduleImmediate(getContext());
                call.resolve(store.publicStatus());
            } catch (Exception exception) {
                call.reject("保存后台同步配置失败：" + exception.getMessage(), "CONFIG_FAILED", exception);
            }
        });
    }

    @PluginMethod
    public void enrollDevice(PluginCall call) {
        String baseUrl = call.getString("baseUrl");
        String enrollmentCode = call.getString("enrollmentCode");
        executor.execute(() -> {
            try {
                JSObject result = VivoAutoSyncClient.enroll(getContext(), baseUrl, enrollmentCode);
                VivoAutoSyncStore store = new VivoAutoSyncStore(getContext());
                boolean scheduled = false;
                try {
                    scheduled = VivoAutoSyncJobService.schedule(getContext());
                } catch (RuntimeException ignored) {
                    // 设备绑定已经成功；个别系统可能暂时拒绝注册持久任务。
                }
                try {
                    VivoAutoSyncJobService.scheduleImmediate(getContext());
                } catch (RuntimeException ignored) {
                    // 绑定凭据已经安全保存，后续可由开机广播或手动同步恢复。
                }
                if (!scheduled) {
                    store.recordConfigured(
                        "设备绑定成功；同步凭据已安全保存，但系统暂未接受后台任务，请在系统设置中允许衡康自启动和后台运行。"
                    );
                }
                call.resolve(store.publicStatus());
            } catch (Exception exception) {
                call.reject("设备绑定失败：" + exception.getMessage(), "ENROLL_FAILED", exception);
            }
        });
    }

    @PluginMethod
    public void getPendingPairing(PluginCall call) {
        android.content.SharedPreferences preferences = getContext()
            .getSharedPreferences("vivo_pairing", android.content.Context.MODE_PRIVATE);
        String payload = preferences.getString("payload", "");
        JSObject result = new JSObject();
        result.put("available", !payload.isEmpty());
        result.put("payload", payload.isEmpty() ? null : payload);
        call.resolve(result);
    }

    @PluginMethod
    public void clearPendingPairing(PluginCall call) {
        getContext()
            .getSharedPreferences("vivo_pairing", android.content.Context.MODE_PRIVATE)
            .edit()
            .remove("payload")
            .apply();
        JSObject result = new JSObject();
        result.put("available", false);
        result.put("payload", null);
        call.resolve(result);
    }

    @PluginMethod
    public void getAutoSyncStatus(PluginCall call) {
        executor.execute(() -> {
            VivoAutoSyncStore store = new VivoAutoSyncStore(getContext());
            try {
                if (VivoAutoSyncStore.isConfigured(getContext())) {
                    boolean scheduled = false;
                    try {
                        scheduled = VivoAutoSyncJobService.schedule(getContext());
                    } catch (RuntimeException ignored) {
                        // 状态查询不能因为厂商后台策略异常而失败。
                    }
                    try {
                        VivoAutoSyncJobService.scheduleImmediate(getContext());
                    } catch (RuntimeException ignored) {
                        // 周期任务仍可在系统允许时恢复，手动同步也继续可用。
                    }
                    if (!scheduled) {
                        store.recordConfigured(
                            "设备已绑定；同步凭据已安全保存，但系统暂未接受后台任务，请在系统设置中允许衡康自启动和后台运行。"
                        );
                    }
                }
                call.resolve(store.publicStatus());
            } catch (Exception exception) {
                call.reject("读取自动同步状态失败：" + exception.getMessage(), "STATUS_FAILED", exception);
            }
        });
    }

    @PluginMethod
    public void syncConfiguredNow(PluginCall call) {
        executor.execute(() -> call.resolve(VivoAutoSyncClient.syncNow(getContext(), true)));
    }

    @PluginMethod
    public void clearAutoSync(PluginCall call) {
        executor.execute(() -> {
            VivoAutoSyncJobService.cancel(getContext());
            VivoAutoSyncStore store = new VivoAutoSyncStore(getContext());
            store.clear();
            call.resolve(store.publicStatus());
        });
    }

    @Override
    protected void handleOnDestroy() {
        executor.shutdownNow();
        super.handleOnDestroy();
    }

    private JSObject getStatusJson(String requestedSessionId) {
        android.content.SharedPreferences preferences = getContext().getSharedPreferences("vivo_overnight_capture", android.content.Context.MODE_PRIVATE);
        String sessionId = preferences.getString("sessionId", requestedSessionId);
        boolean running = preferences.getBoolean("running", false);
        JSObject result = new JSObject();
        result.put("captureStatus", running ? "RUNNING" : "STOPPED");
        result.put("sessionId", sessionId);
        result.put("intervalSeconds", preferences.getInt("intervalSeconds", 60));
        result.put("lastPollAt", preferences.getLong("lastPollAt", 0L));
        result.put("lastSourceTimestamp", preferences.getLong("lastSourceTimestamp", 0L));
        result.put("lastStatus", preferences.getString("lastStatus", "NO_DATA"));
        result.put("lastMessage", preferences.getString("lastMessage", "尚未开始采集"));
            result.put("lastPollCreatedSample", preferences.getBoolean("lastPollCreatedSample", false));
            result.put("lastSnapshotStatus", preferences.getString("lastSnapshotStatus", "NO_DATA"));
            result.put("lastSnapshotMessage", preferences.getString("lastSnapshotMessage", "尚未保存健康快照"));
            VivoHealthSnapshotStore snapshotStore = new VivoHealthSnapshotStore(getContext());
            JSObject snapshotSummary = snapshotStore.summary();
            snapshotStore.close();
            result.put("snapshotCount", snapshotSummary.optInt("snapshotCount", 0));
            result.put("lastSnapshotAt", snapshotSummary.opt("lastSnapshotAt"));
            if (sessionId != null && !sessionId.trim().isEmpty()) {
            VivoOvernightStore store = new VivoOvernightStore(getContext());
            JSObject summary = store.sessionSummary(sessionId);
            store.close();
            result.put("sampleCount", summary.optInt("sampleCount", 0));
            result.put("firstMeasuredAt", summary.opt("firstMeasuredAt"));
            result.put("lastMeasuredAt", summary.opt("lastMeasuredAt"));
        } else {
            result.put("sampleCount", 0);
            result.put("firstMeasuredAt", null);
            result.put("lastMeasuredAt", null);
        }
        return result;
    }
}
