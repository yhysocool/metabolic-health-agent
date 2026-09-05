package com.healthevent.mobile;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;
import com.healthevent.mobile.vivo.VivoOvernightHealthPlugin;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(VivoOvernightHealthPlugin.class);
        super.onCreate(savedInstanceState);
        rememberPairingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        rememberPairingIntent(intent);
    }

    private void rememberPairingIntent(Intent intent) {
        Uri uri = intent == null ? null : intent.getData();
        if (uri == null
            || !"healthevent".equalsIgnoreCase(uri.getScheme())
            || !"pair".equalsIgnoreCase(uri.getHost())
            || uri.getQueryParameter("code") == null
            || uri.getQueryParameter("code").trim().isEmpty()) {
            return;
        }
        getSharedPreferences("vivo_pairing", MODE_PRIVATE)
            .edit()
            .putString("payload", uri.toString())
            .apply();
    }
}
