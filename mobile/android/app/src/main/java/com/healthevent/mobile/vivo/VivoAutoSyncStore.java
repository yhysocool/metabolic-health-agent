package com.healthevent.mobile.vivo;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import com.getcapacitor.JSObject;

import java.net.URL;
import java.security.KeyStore;
import java.util.UUID;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Stores the upload token encrypted by an Android Keystore AES key. */
final class VivoAutoSyncStore {
    static final long MIN_SYNC_INTERVAL_MS = 15L * 60L * 1000L;
    private static final String PREFS = "vivo_auto_sync";
    private static final String KEY_ALIAS = "healthevent_vivo_sync_token_v1";
    private static final String DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001";

    static final class Config {
        final boolean enabled;
        final String baseUrl;
        final String token;
        final String userId;
        final String deviceId;
        final long cursor;

        Config(boolean enabled, String baseUrl, String token, String userId, String deviceId, long cursor) {
            this.enabled = enabled;
            this.baseUrl = baseUrl;
            this.token = token;
            this.userId = userId;
            this.deviceId = deviceId;
            this.cursor = cursor;
        }
    }

    private final Context context;
    private final SharedPreferences preferences;

    VivoAutoSyncStore(Context context) {
        this.context = context.getApplicationContext();
        preferences = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static boolean isConfigured(Context context) {
        try {
            Config config = new VivoAutoSyncStore(context).load();
            return config.enabled && !config.baseUrl.isEmpty() && config.token.length() >= 32;
        } catch (Exception ignored) {
            return false;
        }
    }

    synchronized void configure(String rawBaseUrl, String token, String userId, String cursor) throws Exception {
        saveConfig(rawBaseUrl, token, userId, cursor, getOrCreateDeviceId());
    }

    synchronized void configureProvisioned(
        String rawBaseUrl,
        String token,
        String userId,
        String cursor,
        String deviceId
    ) throws Exception {
        saveConfig(rawBaseUrl, token, userId, cursor, deviceId);
    }

    private void saveConfig(
        String rawBaseUrl,
        String token,
        String userId,
        String cursor,
        String deviceId
    ) throws Exception {
        String baseUrl = normalizeHttpsBaseUrl(rawBaseUrl);
        if (token == null || token.trim().length() < 32) {
            throw new IllegalArgumentException("同步令牌长度至少为 32 个字符");
        }
        if (deviceId == null || deviceId.trim().isEmpty()) {
            throw new IllegalArgumentException("设备身份不能为空");
        }
        String resolvedUserId = userId == null || userId.trim().isEmpty() ? DEFAULT_USER_ID : userId.trim();
        String[] encrypted = encrypt(token.trim());
        SharedPreferences.Editor editor = preferences.edit()
            .putBoolean("enabled", true)
            .putString("baseUrl", baseUrl)
            .putString("tokenIv", encrypted[0])
            .putString("tokenCiphertext", encrypted[1])
            .putString("userId", resolvedUserId)
            .putString("deviceId", deviceId.trim())
            .putString("lastError", "");
        long parsedCursor = parseCursor(cursor);
        if (parsedCursor > 0L) editor.putLong("cursor", parsedCursor);
        editor.apply();
    }

    synchronized Config load() throws Exception {
        String iv = preferences.getString("tokenIv", "");
        String ciphertext = preferences.getString("tokenCiphertext", "");
        String token = iv.isEmpty() || ciphertext.isEmpty() ? "" : decrypt(iv, ciphertext);
        return new Config(
            preferences.getBoolean("enabled", false),
            preferences.getString("baseUrl", ""),
            token,
            preferences.getString("userId", DEFAULT_USER_ID),
            getOrCreateDeviceId(),
            preferences.getLong("cursor", 0L)
        );
    }

    synchronized JSObject publicStatus() {
        JSObject result = new JSObject();
        boolean tokenStored = !preferences.getString("tokenCiphertext", "").isEmpty();
        result.put("enabled", preferences.getBoolean("enabled", false));
        result.put("configured", tokenStored && !preferences.getString("baseUrl", "").isEmpty());
        result.put("baseUrl", preferences.getString("baseUrl", ""));
        result.put("intervalMinutes", 15);
        result.put("lastAttemptAt", nullableLong("lastAttemptAt"));
        result.put("lastSuccessAt", nullableLong("lastSuccessAt"));
        result.put("lastStatus", preferences.getString("lastStatus", "NO_DATA"));
        result.put("lastMessage", preferences.getString("lastMessage", "尚未执行后台同步"));
        result.put("lastCreated", preferences.getInt("lastCreated", 0));
        result.put("lastUpdated", preferences.getInt("lastUpdated", 0));
        result.put("lastUnchanged", preferences.getInt("lastUnchanged", 0));
        result.put("cursor", preferences.getLong("cursor", 0L) > 0L
            ? String.valueOf(preferences.getLong("cursor", 0L)) : null);
        return result;
    }

    synchronized void recordAttempt() {
        preferences.edit().putLong("lastAttemptAt", System.currentTimeMillis()).apply();
    }

    synchronized void recordSuccess(long cursor, int created, int updated, int unchanged, String message) {
        preferences.edit()
            .putLong("cursor", Math.max(cursor, preferences.getLong("cursor", 0L)))
            .putLong("lastSuccessAt", System.currentTimeMillis())
            .putString("lastStatus", "PASS")
            .putString("lastMessage", message)
            .putString("lastError", "")
            .putInt("lastCreated", created)
            .putInt("lastUpdated", updated)
            .putInt("lastUnchanged", unchanged)
            .apply();
    }

    synchronized void recordError(String message) {
        preferences.edit()
            .putString("lastStatus", "ERROR")
            .putString("lastMessage", message)
            .putString("lastError", message)
            .apply();
    }

    synchronized void recordConfigured(String message) {
        preferences.edit()
            .putString("lastStatus", "NO_DATA")
            .putString("lastMessage", message)
            .putString("lastError", "")
            .apply();
    }

    synchronized void clear() {
        preferences.edit().clear().apply();
    }

    synchronized long lastAttemptAt() {
        return preferences.getLong("lastAttemptAt", 0L);
    }

    private Object nullableLong(String key) {
        long value = preferences.getLong(key, 0L);
        return value > 0L ? value : null;
    }

    static String getOrCreateDeviceId(Context context) {
        SharedPreferences devicePreferences = context.getApplicationContext()
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String existing = devicePreferences.getString("deviceId", "");
        if (!existing.isEmpty()) return existing;
        String created = UUID.randomUUID().toString();
        devicePreferences.edit().putString("deviceId", created).apply();
        return created;
    }

    private String getOrCreateDeviceId() {
        return getOrCreateDeviceId(context);
    }

    private static long parseCursor(String cursor) {
        if (cursor == null || cursor.trim().isEmpty()) return 0L;
        try {
            return Long.parseLong(cursor.trim());
        } catch (NumberFormatException ignored) {
            return 0L;
        }
    }

    static String normalizeHttpsBaseUrl(String rawValue) throws Exception {
        if (rawValue == null || rawValue.trim().isEmpty()) {
            throw new IllegalArgumentException("服务器地址不能为空");
        }
        URL url = new URL(rawValue.trim());
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getHost().isEmpty()) {
            throw new IllegalArgumentException("后台健康同步只允许 HTTPS 地址");
        }
        if (url.getUserInfo() != null || !url.getPath().matches("/?") || url.getQuery() != null || url.getRef() != null) {
            throw new IllegalArgumentException("服务器地址只能填写 HTTPS 根地址");
        }
        int port = url.getPort();
        String normalized = "https://" + url.getHost() + (port == -1 || port == 443 ? "" : ":" + port);
        return normalized;
    }

    private static SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        java.security.Key key = keyStore.getKey(KEY_ALIAS, null);
        if (key instanceof SecretKey) return (SecretKey) key;

        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .build());
        return generator.generateKey();
    }

    private static String[] encrypt(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] ciphertext = cipher.doFinal(value.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        return new String[]{
            Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP),
            Base64.encodeToString(ciphertext, Base64.NO_WRAP),
        };
    }

    private static String decrypt(String ivValue, String ciphertextValue) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        GCMParameterSpec spec = new GCMParameterSpec(128, Base64.decode(ivValue, Base64.NO_WRAP));
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), spec);
        byte[] plaintext = cipher.doFinal(Base64.decode(ciphertextValue, Base64.NO_WRAP));
        return new String(plaintext, java.nio.charset.StandardCharsets.UTF_8);
    }
}
