package com.healthevent.mobile.vivo;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.util.Log;

import com.getcapacitor.JSObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Persistent, network-aware 15-minute scheduler for encrypted vivo uploads. */
public final class VivoAutoSyncJobService extends JobService {
    private static final String TAG = "VivoAutoSyncJob";
    private static final int PERIODIC_JOB_ID = 2404;
    private static final int IMMEDIATE_JOB_ID = 2405;
    private ExecutorService executor;

    static boolean schedule(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        ComponentName component = new ComponentName(context, VivoAutoSyncJobService.class);
        try {
            JobInfo periodic = new JobInfo.Builder(PERIODIC_JOB_ID, component)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(VivoAutoSyncStore.MIN_SYNC_INTERVAL_MS)
                .setBackoffCriteria(60_000L, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
                .build();
            int result = scheduler.schedule(periodic);
            Log.i(TAG, "persisted_schedule_result=" + result);
            if (result == JobScheduler.RESULT_SUCCESS) {
                return true;
            }
        } catch (RuntimeException exception) {
            Log.w(
                TAG,
                "persisted_schedule_exception=" + exception.getClass().getSimpleName()
                    + ":" + exception.getMessage()
            );
            // 某些 Android 版本/厂商系统会拒绝 setPersisted(true) 的任务。
        }

        // 某些厂商系统连非持久化周期任务也会拒绝，改用单次延迟任务。
        // 任务完成后会再次预约；开机广播也会重新预约，因此无需用户再次打开 App。
        try {
            JobInfo fallback = new JobInfo.Builder(PERIODIC_JOB_ID, component)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setMinimumLatency(VivoAutoSyncStore.MIN_SYNC_INTERVAL_MS)
                .setOverrideDeadline(VivoAutoSyncStore.MIN_SYNC_INTERVAL_MS + 5L * 60L * 1000L)
                .setBackoffCriteria(60_000L, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
                .build();
            int result = scheduler.schedule(fallback);
            Log.i(TAG, "delayed_schedule_result=" + result);
            return result == JobScheduler.RESULT_SUCCESS;
        } catch (RuntimeException exception) {
            Log.w(
                TAG,
                "delayed_schedule_exception=" + exception.getClass().getSimpleName()
                    + ":" + exception.getMessage()
            );
            return false;
        }
    }

    static void scheduleImmediate(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        ComponentName component = new ComponentName(context, VivoAutoSyncJobService.class);
        JobInfo immediate = new JobInfo.Builder(IMMEDIATE_JOB_ID, component)
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
            .setMinimumLatency(0L)
            .setOverrideDeadline(10_000L)
            .setBackoffCriteria(60_000L, JobInfo.BACKOFF_POLICY_EXPONENTIAL)
            .build();
        scheduler.schedule(immediate);
    }

    static void cancel(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        scheduler.cancel(PERIODIC_JOB_ID);
        scheduler.cancel(IMMEDIATE_JOB_ID);
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        executor = Executors.newSingleThreadExecutor();
        executor.execute(() -> {
            boolean shouldRetry = false;
            if (VivoAutoSyncClient.shouldRun(this)) {
                JSObject result = VivoAutoSyncClient.syncNow(this, true);
                shouldRetry = "ERROR".equals(result.optString("lastStatus"));
            }
            jobFinished(params, shouldRetry);
            if (VivoAutoSyncStore.isConfigured(this)) {
                VivoAutoSyncJobService.schedule(this);
            }
        });
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (executor != null) executor.shutdownNow();
        return true;
    }

    @Override
    public void onDestroy() {
        if (executor != null) executor.shutdownNow();
        super.onDestroy();
    }
}
