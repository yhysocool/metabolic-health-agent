package com.healthevent.mobile.vivo;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * App-private history for complete vivo Provider snapshots.
 *
 * <p>The existing overnight table remains the normalized SpO2 table. This
 * store keeps the complete, lossless Provider payload so fields that are not
 * yet mapped by the UI or AI layer are not discarded.</p>
 */
public final class VivoHealthSnapshotStore extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "vivo_health_snapshots.db";
    private static final int DATABASE_VERSION = 1;
    private static final String TABLE = "health_snapshots";

    public VivoHealthSnapshotStore(Context context) {
        super(context.getApplicationContext(), DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase database) {
        database.execSQL(
            "CREATE TABLE " + TABLE + " (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "read_at INTEGER NOT NULL," +
                "status TEXT NOT NULL," +
                "fingerprint TEXT NOT NULL UNIQUE," +
                "payload_json TEXT NOT NULL," +
                "synced_at INTEGER NOT NULL" +
            ")"
        );
        database.execSQL("CREATE INDEX idx_health_snapshots_read_at ON " + TABLE + "(read_at DESC)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase database, int oldVersion, int newVersion) {
        // Keep future migrations explicit; do not delete existing health data.
    }

    public synchronized JSObject saveIfChanged(JSObject snapshot) {
        JSObject result = new JSObject();
        String payload = snapshot.toString();
        String fingerprint = fingerprint(snapshot);
        long readAt = snapshot.optLong("readAtEpochMs", System.currentTimeMillis());
        String status = snapshotStatus(snapshot);
        ContentValues values = new ContentValues();
        values.put("read_at", readAt);
        values.put("status", status);
        values.put("fingerprint", fingerprint);
        values.put("payload_json", payload);
        values.put("synced_at", System.currentTimeMillis());

        try {
            long id = getWritableDatabase().insertWithOnConflict(
                TABLE,
                null,
                values,
                SQLiteDatabase.CONFLICT_IGNORE
            );
            result.put("status", "PASS");
            result.put("persisted", id != -1L);
            result.put("duplicate", id == -1L);
            result.put("snapshotId", id == -1L ? null : id);
            result.put("message", id == -1L ? "健康快照未变化，未重复保存" : "健康快照已保存");
        } catch (Exception exception) {
            result.put("status", "ERROR");
            result.put("persisted", false);
            result.put("duplicate", false);
            result.put("message", "健康快照保存失败：" + exception.getClass().getSimpleName());
        }
        result.put("readAt", readAt);
        result.put("fingerprint", fingerprint);
        return result;
    }

    public synchronized JSObject summary() {
        JSObject result = new JSObject();
        result.put("status", "PASS");
        result.put("snapshotCount", 0);
        result.put("lastSnapshotAt", null);
        try (Cursor cursor = getReadableDatabase().rawQuery(
            "SELECT COUNT(*) AS snapshot_count, MAX(read_at) AS last_at FROM " + TABLE,
            null
        )) {
            if (cursor.moveToFirst()) {
                result.put("snapshotCount", cursor.getInt(cursor.getColumnIndexOrThrow("snapshot_count")));
                if (!cursor.isNull(cursor.getColumnIndexOrThrow("last_at"))) {
                    result.put("lastSnapshotAt", cursor.getLong(cursor.getColumnIndexOrThrow("last_at")));
                }
            }
        }
        return result;
    }

    public synchronized JSObject readRecent(int requestedLimit) {
        int limit = Math.max(1, Math.min(requestedLimit, 1000));
        JSArray items = new JSArray();
        try (Cursor cursor = getReadableDatabase().query(
            TABLE,
            new String[]{"id", "read_at", "status", "payload_json", "synced_at"},
            null,
            null,
            null,
            null,
            "read_at DESC",
            String.valueOf(limit)
        )) {
            while (cursor.moveToNext()) {
                JSObject item = new JSObject();
                item.put("id", cursor.getLong(cursor.getColumnIndexOrThrow("id")));
                item.put("readAt", cursor.getLong(cursor.getColumnIndexOrThrow("read_at")));
                item.put("status", cursor.getString(cursor.getColumnIndexOrThrow("status")));
                item.put("payload", new JSONObject(cursor.getString(cursor.getColumnIndexOrThrow("payload_json"))));
                item.put("syncedAt", cursor.getLong(cursor.getColumnIndexOrThrow("synced_at")));
                items.put(item);
            }
        } catch (Exception exception) {
            JSObject error = new JSObject();
            error.put("status", "ERROR");
            error.put("message", "读取健康快照历史失败：" + exception.getClass().getSimpleName());
            error.put("items", items);
            return error;
        }
        JSObject result = new JSObject();
        result.put("status", "PASS");
        result.put("items", items);
        return result;
    }

    public synchronized JSObject readAfter(long cursor, int requestedLimit) {
        int limit = Math.max(1, Math.min(requestedLimit, 1000));
        JSArray items = new JSArray();
        try (Cursor databaseCursor = getReadableDatabase().query(
            TABLE,
            new String[]{"id", "read_at", "status", "payload_json", "synced_at"},
            "read_at > ?",
            new String[]{String.valueOf(Math.max(0L, cursor))},
            null,
            null,
            "read_at ASC",
            String.valueOf(limit)
        )) {
            while (databaseCursor.moveToNext()) {
                JSObject item = new JSObject();
                item.put("id", databaseCursor.getLong(databaseCursor.getColumnIndexOrThrow("id")));
                item.put("readAt", databaseCursor.getLong(databaseCursor.getColumnIndexOrThrow("read_at")));
                item.put("status", databaseCursor.getString(databaseCursor.getColumnIndexOrThrow("status")));
                item.put("payload", new JSONObject(databaseCursor.getString(databaseCursor.getColumnIndexOrThrow("payload_json"))));
                item.put("syncedAt", databaseCursor.getLong(databaseCursor.getColumnIndexOrThrow("synced_at")));
                items.put(item);
            }
        } catch (Exception exception) {
            JSObject error = new JSObject();
            error.put("status", "ERROR");
            error.put("message", "读取待同步健康快照失败：" + exception.getClass().getSimpleName());
            error.put("items", items);
            return error;
        }
        JSObject result = new JSObject();
        result.put("status", "PASS");
        result.put("items", items);
        return result;
    }

    private static String snapshotStatus(JSObject snapshot) {
        JSONObject activity = snapshot.optJSONObject("activity");
        JSONObject privateHealth = snapshot.optJSONObject("privateHealth");
        String privateStatus = privateHealth == null ? "" : privateHealth.optString("status", "");
        String activityStatus = activity == null ? "" : activity.optString("status", "");
        if (VivoSpO2Reading.PASS.equals(privateStatus) || VivoSpO2Reading.PASS.equals(activityStatus)) {
            return VivoSpO2Reading.PASS;
        }
        if (!privateStatus.isEmpty()) return privateStatus;
        if (!activityStatus.isEmpty()) return activityStatus;
        return VivoSpO2Reading.NO_DATA;
    }

    private static String fingerprint(JSObject snapshot) {
        try {
            JSONObject copy = new JSONObject(snapshot.toString());
            copy.remove("readAtEpochMs");
            copy.remove("readAt");
            JSONObject activity = copy.optJSONObject("activity");
            if (activity != null) {
                activity.remove("sampleEpochMs");
                activity.remove("sampledAt");
            }
            JSONObject privateHealth = copy.optJSONObject("privateHealth");
            if (privateHealth != null) {
                privateHealth.remove("readAtEpochMs");
                privateHealth.remove("readAt");
            }
            org.json.JSONArray observations = copy.optJSONArray("observations");
            if (observations != null) {
                for (int index = 0; index < observations.length(); index++) {
                    JSONObject observation = observations.optJSONObject(index);
                    if (observation != null) observation.remove("syncedAt");
                }
            }
            return sha256(copy.toString());
        } catch (Exception exception) {
            return sha256(snapshot.toString());
        }
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(bytes.length * 2);
            for (byte item : bytes) result.append(String.format("%02x", item));
            return result.toString();
        } catch (NoSuchAlgorithmException exception) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
