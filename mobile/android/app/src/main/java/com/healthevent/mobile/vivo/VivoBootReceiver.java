package com.healthevent.mobile.vivo;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import androidx.core.content.ContextCompat;

/**
 * Restores the configured sync job and a previously running capture session
 * after boot or an application update.
 */
public final class VivoBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
            && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
            return;
        }

        Context appContext = context.getApplicationContext();
        if (VivoAutoSyncStore.isConfigured(appContext)) {
            VivoAutoSyncJobService.schedule(appContext);
            VivoAutoSyncJobService.scheduleImmediate(appContext);
        }

        SharedPreferences preferences = appContext.getSharedPreferences(
            "vivo_overnight_capture",
            Context.MODE_PRIVATE
        );
        if (!preferences.getBoolean("running", false)) return;

        Intent serviceIntent = new Intent(appContext, VivoOvernightCaptureService.class);
        serviceIntent.setAction(VivoOvernightCaptureService.ACTION_START);
        serviceIntent.putExtra(
            VivoOvernightCaptureService.EXTRA_INTERVAL_SECONDS,
            preferences.getInt("intervalSeconds", 60)
        );
        serviceIntent.putExtra(
            VivoOvernightCaptureService.EXTRA_SESSION_ID,
            preferences.getString("sessionId", VivoOvernightStore.newSessionId())
        );
        try {
            ContextCompat.startForegroundService(appContext, serviceIntent);
        } catch (RuntimeException exception) {
            preferences.edit()
                .putBoolean("running", false)
                .putString("lastStatus", VivoSpO2Reading.ERROR)
                .putString("lastMessage", "系统阻止开机后恢复健康采集，请打开衡康重新启动")
                .apply();
        }
    }
}
