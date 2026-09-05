package com.healthevent.mobile.vivo;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;

import java.util.List;
import java.util.UUID;

/** Local, app-private store for raw overnight SpO2 observations. */
public final class VivoOvernightStore extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "vivo_overnight_health.db";
    private static final int DATABASE_VERSION = 2;
    private static final String TABLE = "health_observations";

    public VivoOvernightStore(Context context) {
        super(context.getApplicationContext(), DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase database) {
        database.execSQL(
            "CREATE TABLE " + TABLE + " (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "session_id TEXT NOT NULL," +
                "source TEXT NOT NULL," +
                "source_device TEXT NOT NULL," +
                "metric_type TEXT NOT NULL," +
                "measured_at INTEGER NOT NULL," +
                "start_time INTEGER NOT NULL," +
                "end_time INTEGER NOT NULL," +
                "value REAL NOT NULL," +
                "unit TEXT NOT NULL," +
                "status TEXT NOT NULL," +
                "raw_source TEXT NOT NULL," +
                "synced_at INTEGER NOT NULL," +
                "uploaded_at INTEGER," +
                "UNIQUE(metric_type, source_device, measured_at)" +
            ")"
        );
        database.execSQL("CREATE INDEX idx_health_observations_session ON " + TABLE + "(session_id, measured_at)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase database, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            database.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN uploaded_at INTEGER");
        }
    }

    public synchronized boolean insertIfNew(String sessionId, VivoSpO2Reading reading) {
        if (!VivoSpO2Reading.PASS.equals(reading.status) || reading.measuredAt <= 0L) {
            return false;
        }
        ContentValues values = new ContentValues();
        values.put("session_id", sessionId);
        values.put("source", "vivo_local_health_provider");
        values.put("source_device", "vivo_health_provider");
        values.put("metric_type", "spo2");
        values.put("measured_at", reading.measuredAt);
        values.put("start_time", reading.measuredAt);
        values.put("end_time", reading.measuredAt);
        values.put("value", reading.value);
        values.put("unit", "%");
        values.put("status", reading.status);
        values.put("raw_source", reading.rawSource);
        values.put("synced_at", System.currentTimeMillis());
        values.putNull("uploaded_at");
        return getWritableDatabase().insertWithOnConflict(TABLE, null, values, SQLiteDatabase.CONFLICT_IGNORE) != -1L;
    }

    public synchronized JSArray readSession(String sessionId) {
        return readRecords("session_id = ?", new String[]{sessionId}, 0);
    }

    public synchronized JSArray readAll(int requestedLimit) {
        return readRecords(null, null, requestedLimit);
    }

    public synchronized JSArray readPending(int requestedLimit) {
        return readRecords("uploaded_at IS NULL", null, requestedLimit);
    }

    private JSArray readRecords(String selection, String[] selectionArgs, int requestedLimit) {
        JSArray result = new JSArray();
        String limit = requestedLimit > 0
            ? String.valueOf(Math.max(1, Math.min(requestedLimit, 1000)))
            : null;
        try (Cursor cursor = getReadableDatabase().query(
            TABLE,
            null,
            selection,
            selectionArgs,
            null,
            null,
            "measured_at ASC",
            limit
        )) {
            while (cursor.moveToNext()) {
                JSObject item = new JSObject();
                item.put("id", cursor.getLong(cursor.getColumnIndexOrThrow("id")));
                item.put("sessionId", cursor.getString(cursor.getColumnIndexOrThrow("session_id")));
                item.put("source", cursor.getString(cursor.getColumnIndexOrThrow("source")));
                item.put("sourceDevice", cursor.getString(cursor.getColumnIndexOrThrow("source_device")));
                item.put("metricType", cursor.getString(cursor.getColumnIndexOrThrow("metric_type")));
                item.put("measuredAt", cursor.getLong(cursor.getColumnIndexOrThrow("measured_at")));
                item.put("startTime", cursor.getLong(cursor.getColumnIndexOrThrow("start_time")));
                item.put("endTime", cursor.getLong(cursor.getColumnIndexOrThrow("end_time")));
                item.put("value", cursor.getDouble(cursor.getColumnIndexOrThrow("value")));
                item.put("unit", cursor.getString(cursor.getColumnIndexOrThrow("unit")));
                item.put("status", cursor.getString(cursor.getColumnIndexOrThrow("status")));
                item.put("rawSource", cursor.getString(cursor.getColumnIndexOrThrow("raw_source")));
                item.put("syncedAt", cursor.getLong(cursor.getColumnIndexOrThrow("synced_at")));
                int uploadedAtIndex = cursor.getColumnIndexOrThrow("uploaded_at");
                item.put("uploadedAt", cursor.isNull(uploadedAtIndex) ? null : cursor.getLong(uploadedAtIndex));
                result.put(item);
            }
        }
        return result;
    }

    public synchronized int markUploaded(List<Long> ids) {
        if (ids == null || ids.isEmpty()) return 0;
        SQLiteDatabase database = getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("uploaded_at", System.currentTimeMillis());
        int updated = 0;
        database.beginTransaction();
        try {
            for (Long id : ids) {
                if (id == null || id <= 0L) continue;
                updated += database.update(
                    TABLE,
                    values,
                    "id = ? AND uploaded_at IS NULL",
                    new String[]{String.valueOf(id)}
                );
            }
            database.setTransactionSuccessful();
        } finally {
            database.endTransaction();
        }
        return updated;
    }

    public synchronized JSObject sessionSummary(String sessionId) {
        JSObject result = new JSObject();
        result.put("sessionId", sessionId);
        result.put("sampleCount", 0);
        result.put("firstMeasuredAt", null);
        result.put("lastMeasuredAt", null);
        try (Cursor cursor = getReadableDatabase().rawQuery(
            "SELECT COUNT(*) AS sample_count, MIN(measured_at) AS first_at, MAX(measured_at) AS last_at FROM " + TABLE + " WHERE session_id = ?",
            new String[]{sessionId}
        )) {
            if (cursor.moveToFirst()) {
                result.put("sampleCount", cursor.getInt(cursor.getColumnIndexOrThrow("sample_count")));
                if (!cursor.isNull(cursor.getColumnIndexOrThrow("first_at"))) {
                    result.put("firstMeasuredAt", cursor.getLong(cursor.getColumnIndexOrThrow("first_at")));
                }
                if (!cursor.isNull(cursor.getColumnIndexOrThrow("last_at"))) {
                    result.put("lastMeasuredAt", cursor.getLong(cursor.getColumnIndexOrThrow("last_at")));
                }
            }
        }
        return result;
    }

    public static String newSessionId() {
        return UUID.randomUUID().toString();
    }
}
