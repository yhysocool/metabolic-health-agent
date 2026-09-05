package com.healthevent.mobile.vivo;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import androidx.core.content.ContextCompat;

import com.healthevent.mobile.MainActivity;

import com.getcapacitor.JSObject;

import org.json.JSONObject;
import org.json.JSONArray;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * User-started foreground poller that can be restored after process death or
 * reboot. Android may still stop it under severe battery policies; every poll
 * and source timestamp is persisted explicitly.
 */
public final class VivoOvernightCaptureService extends Service {
    public static final String ACTION_START = "com.healthevent.mobile.vivo.START_SPO2";
    public static final String ACTION_STOP = "com.healthevent.mobile.vivo.STOP_SPO2";
    public static final String EXTRA_INTERVAL_SECONDS = "intervalSeconds";
    public static final String EXTRA_SESSION_ID = "sessionId";
    private static final String PREFS = "vivo_overnight_capture";
    private static final String CHANNEL_ID = "vivo_overnight_capture";
    private static final int NOTIFICATION_ID = 2401;
    private static final int DEFAULT_INTERVAL_SECONDS = 60;
    private static final int MIN_INTERVAL_SECONDS = 60;
    private static final int MAX_INTERVAL_SECONDS = 600;

    private ScheduledExecutorService executor;
    private VivoOvernightStore store;
    private VivoHealthSnapshotStore snapshotStore;

    public static void start(Context context, int intervalSeconds, String sessionId) {
        Intent intent = new Intent(context, VivoOvernightCaptureService.class);
        intent.setAction(ACTION_START);
        intent.putExtra(EXTRA_INTERVAL_SECONDS, clampInterval(intervalSeconds));
        intent.putExtra(EXTRA_SESSION_ID, sessionId);
        ContextCompat.startForegroundService(context, intent);
    }

    public static void stop(Context context) {
        Intent intent = new Intent(context, VivoOvernightCaptureService.class);
        intent.setAction(ACTION_STOP);
        context.startService(intent);
    }

    @Override
    public void onCreate() {
        super.onCreate();
        store = new VivoOvernightStore(this);
        snapshotStore = new VivoHealthSnapshotStore(this);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopCapture();
            return START_NOT_STICKY;
        }

        int intervalSeconds = DEFAULT_INTERVAL_SECONDS;
        String sessionId = VivoOvernightStore.newSessionId();
        if (intent != null) {
            intervalSeconds = clampInterval(intent.getIntExtra(EXTRA_INTERVAL_SECONDS, DEFAULT_INTERVAL_SECONDS));
            String requestedSessionId = intent.getStringExtra(EXTRA_SESSION_ID);
            if (requestedSessionId != null && !requestedSessionId.trim().isEmpty()) {
                sessionId = requestedSessionId;
            }
        }
        getPreferences().edit()
            .putBoolean("running", true)
            .putString("sessionId", sessionId)
            .putInt("intervalSeconds", intervalSeconds)
            .apply();

        try {
            startForeground(NOTIFICATION_ID, buildNotification("正在等待 vivo 血氧观测点"));
        } catch (SecurityException exception) {
            getPreferences().edit()
                .putBoolean("running", false)
                .putString("lastStatus", VivoSpO2Reading.ERROR)
                .putString("lastMessage", "系统拒绝启动健康前台服务，请检查通知和前台服务权限")
                .apply();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (executor != null) {
            executor.shutdownNow();
        }
        executor = Executors.newSingleThreadScheduledExecutor();
        final String activeSessionId = sessionId;
        final int activeIntervalSeconds = intervalSeconds;
        executor.scheduleAtFixedRate(
            () -> poll(activeSessionId),
            0L,
            activeIntervalSeconds,
            TimeUnit.SECONDS
        );
        return START_REDELIVER_INTENT;
    }

    private void poll(String sessionId) {
        long pollAt = System.currentTimeMillis();
        JSObject snapshot = VivoHealthSnapshotReader.read(this);
        JSObject snapshotPersistence = snapshotStore.saveIfChanged(snapshot);
        List<VivoSpO2Reading> readings = readSpO2ReadingsFromSnapshot(snapshot);
        VivoSpO2Reading reading = newestReading(readings);
        long lastSourceTimestamp = getPreferences().getLong("lastSourceTimestamp", 0L);
        boolean newSample = false;
        long highestInsertedTimestamp = lastSourceTimestamp;
        for (VivoSpO2Reading candidate : readings) {
            if (VivoSpO2Reading.PASS.equals(candidate.status) && candidate.measuredAt > lastSourceTimestamp) {
                boolean inserted = store.insertIfNew(sessionId, candidate);
                newSample = newSample || inserted;
                if (inserted && candidate.measuredAt > highestInsertedTimestamp) {
                    highestInsertedTimestamp = candidate.measuredAt;
                }
            }
        }
        if (highestInsertedTimestamp > lastSourceTimestamp) {
            getPreferences().edit().putLong("lastSourceTimestamp", highestInsertedTimestamp).apply();
        }
        getPreferences().edit()
            .putLong("lastPollAt", pollAt)
            .putString("lastStatus", reading.status)
            .putString("lastMessage", reading.message)
            .putBoolean("lastPollCreatedSample", newSample)
            .putString("lastSnapshotStatus", snapshotPersistence.optString("status", "ERROR"))
            .putString("lastSnapshotMessage", snapshotPersistence.optString("message", "健康快照未保存"))
            .apply();

        int sampleCount = store.sessionSummary(sessionId).optInt("sampleCount", 0);
        int snapshotCount = snapshotStore.summary().optInt("snapshotCount", 0);
        updateNotification(sampleCount, snapshotCount, reading, newSample, snapshotPersistence);
    }

    static int persistSnapshotObservations(
        VivoOvernightStore store,
        JSObject snapshot,
        String sessionId
    ) {
        int insertedCount = 0;
        for (VivoSpO2Reading candidate : readSpO2ReadingsFromSnapshot(snapshot)) {
            if (VivoSpO2Reading.PASS.equals(candidate.status)
                && store.insertIfNew(sessionId, candidate)) {
                insertedCount++;
            }
        }
        return insertedCount;
    }

    private void stopCapture() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        getPreferences().edit().putBoolean("running", false).apply();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    @Override
    public void onDestroy() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        getPreferences().edit().putBoolean("running", false).apply();
        if (store != null) {
            store.close();
        }
        if (snapshotStore != null) {
            snapshotStore.close();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private android.content.SharedPreferences getPreferences() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "夜间血氧采集",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("用户主动开启的 vivo 血氧采集实验");
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String text) {
        Intent openIntent = new Intent(this, MainActivity.class);
        int pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            pendingFlags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, openIntent, pendingFlags);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);
        return builder
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setContentTitle("衡康：夜间血氧采集中")
            .setContentText(text)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .build();
    }

    private void updateNotification(
        int sampleCount,
        int snapshotCount,
        VivoSpO2Reading reading,
        boolean newSample,
        JSObject snapshotPersistence
    ) {
        String text = newSample
            ? "已保存 " + sampleCount + " 个新血氧点；快照 " + snapshotCount + " 条"
            : reading.message + "；血氧 " + sampleCount + " 点，快照 " + snapshotCount + " 条";
        if ("ERROR".equals(snapshotPersistence.optString("status"))) {
            text = "快照保存异常；" + text;
        }
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        manager.notify(NOTIFICATION_ID, buildNotification(text));
    }

    private static List<VivoSpO2Reading> readSpO2ReadingsFromSnapshot(JSObject snapshot) {
        List<VivoSpO2Reading> result = new ArrayList<>();
        try {
            JSONObject privateHealth = snapshot.optJSONObject("privateHealth");
            JSONObject vitals = privateHealth == null ? null : privateHealth.optJSONObject("vitals");
            JSONObject spo2 = vitals == null ? null : vitals.optJSONObject("spo2");
            if (spo2 == null) {
                result.add(VivoSpO2Reading.ofStatus(VivoSpO2Reading.UNSUPPORTED, "快照中没有血氧字段", "vivo_health_provider.care/healthCare:MYSELF_DATA"));
                return result;
            }
            JSONArray history = vitals.optJSONArray("spo2History");
            if (history != null) {
                for (int index = 0; index < history.length(); index++) {
                    JSONObject item = history.optJSONObject(index);
                    VivoSpO2Reading reading = parseSpO2Item(item);
                    if (reading != null) result.add(reading);
                }
            }
            if (!result.isEmpty()) return result;
            String status = spo2.optString("status", VivoSpO2Reading.ERROR);
            Double value = number(spo2.opt("value"));
            Long measuredAt = numberAsLong(spo2.opt("sourceEpochMs"));
            if (VivoSpO2Reading.PASS.equals(status) && value != null && measuredAt != null && measuredAt > 0L) result.add(VivoSpO2Reading.pass(value, measuredAt, "vivo_health_provider.care/healthCare:MYSELF_DATA.saO2Value"));
            else result.add(VivoSpO2Reading.ofStatus(status, spo2.optString("message", "Provider 当前没有有效血氧数据"), "vivo_health_provider.care/healthCare:MYSELF_DATA.saO2Value"));
            return result;
        } catch (Exception exception) {
            result.add(VivoSpO2Reading.ofStatus(VivoSpO2Reading.ERROR, "从健康快照解析血氧失败：" + exception.getClass().getSimpleName(), "vivo_health_provider.care/healthCare:MYSELF_DATA.saO2Value"));
            return result;
        }
    }

    private static VivoSpO2Reading parseSpO2Item(JSONObject item) {
        if (item == null) return null;
        String status = item.optString("status", VivoSpO2Reading.ERROR);
        Double value = number(item.opt("value"));
        Long measuredAt = numberAsLong(item.opt("sourceEpochMs"));
        if (!VivoSpO2Reading.PASS.equals(status) || value == null || measuredAt == null || measuredAt <= 0L) return null;
        return VivoSpO2Reading.pass(value, measuredAt, "vivo_health_provider.care/healthCare:MYSELF_DATA.saO2Value");
    }

    private static VivoSpO2Reading newestReading(List<VivoSpO2Reading> readings) {
        VivoSpO2Reading newest = null;
        for (VivoSpO2Reading reading : readings) {
            if (!VivoSpO2Reading.PASS.equals(reading.status)) continue;
            if (newest == null || reading.measuredAt > newest.measuredAt) newest = reading;
        }
        return newest != null ? newest : (readings.isEmpty()
            ? VivoSpO2Reading.ofStatus(VivoSpO2Reading.NO_DATA, "Provider 当前没有血氧数据", "vivo_health_provider.care/healthCare:MYSELF_DATA")
            : readings.get(0));
    }

    private static Double number(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        if (value instanceof Number) return ((Number) value).doubleValue();
        try { return Double.parseDouble(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static Long numberAsLong(Object value) {
        if (value == null || JSONObject.NULL.equals(value)) return null;
        if (value instanceof Number) return ((Number) value).longValue();
        try { return Long.parseLong(String.valueOf(value)); }
        catch (NumberFormatException exception) { return null; }
    }

    private static int clampInterval(int seconds) {
        if (seconds < MIN_INTERVAL_SECONDS) return MIN_INTERVAL_SECONDS;
        return Math.min(seconds, MAX_INTERVAL_SECONDS);
    }
}
