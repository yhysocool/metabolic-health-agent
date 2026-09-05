package com.healthevent.mobile.vivo;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;

/** Creates a device identity whose private key never leaves Android Keystore. */
final class VivoDeviceIdentityStore {
    private static final String KEY_ALIAS = "healthevent_vivo_device_identity_v1";

    private VivoDeviceIdentityStore() {}

    static String deviceId(Context context) {
        return VivoAutoSyncStore.getOrCreateDeviceId(context);
    }

    static String publicKey(Context context) throws Exception {
        return encode(getKeyPair().getPublic().getEncoded());
    }

    static String signEnrollment(Context context, String enrollmentCode) throws Exception {
        String deviceId = deviceId(context);
        Signature signer = Signature.getInstance("SHA256withECDSA");
        signer.initSign(getKeyPair().getPrivate());
        signer.update(VivoDeviceEnrollmentMessage.build(enrollmentCode, deviceId));
        return encode(signer.sign());
    }

    private static KeyPair getKeyPair() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        java.security.Key key = keyStore.getKey(KEY_ALIAS, null);
        java.security.cert.Certificate certificate = keyStore.getCertificate(KEY_ALIAS);
        if (key instanceof PrivateKey && certificate != null) {
            PublicKey publicKey = certificate.getPublicKey();
            return new KeyPair(publicKey, (PrivateKey) key);
        }

        KeyPairGenerator generator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC,
            "AndroidKeyStore"
        );
        generator.initialize(new KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY
        )
            .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .build());
        return generator.generateKeyPair();
    }

    private static String encode(byte[] bytes) {
        return Base64.encodeToString(
            bytes,
            Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING
        );
    }

    static final class VivoDeviceEnrollmentMessage {
        private VivoDeviceEnrollmentMessage() {}

        static byte[] build(String enrollmentCode, String deviceId) {
            return (
                "HEALTH_EVENT_DEVICE_ENROLL_V1\n"
                    + enrollmentCode.trim()
                    + "\n"
                    + deviceId.trim()
            ).getBytes(StandardCharsets.UTF_8);
        }
    }
}
