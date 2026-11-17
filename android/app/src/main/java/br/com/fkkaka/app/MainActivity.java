package br.com.fkkaka.app;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.*;
import android.widget.*;

public final class MainActivity extends Activity {
    private static final String HOME = "https://triade2-0.onrender.com/kaka/";
    private static final int PICK_FILE = 42;
    private WebView web;
    private ProgressBar progress;
    private LinearLayout error;
    private ValueCallback<Uri[]> fileCallback;
    private String retryUrl = HOME;
    private boolean failed;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(11,13,15));
        setContentView(root);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setContentDescription("Carregando página");
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));
        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(11,13,15));
        content.addView(web, new FrameLayout.LayoutParams(-1,-1));
        error = new LinearLayout(this);
        error.setOrientation(LinearLayout.VERTICAL);
        error.setGravity(Gravity.CENTER);
        error.setPadding(dp(24),dp(24),dp(24),dp(24));
        error.setBackgroundColor(Color.rgb(11,13,15));
        TextView message = new TextView(this);
        message.setText("Não foi possível abrir esta página.\n\nConfira sua conexão e tente novamente. O servidor também pode estar iniciando.");
        message.setTextSize(18); message.setTextColor(Color.WHITE); message.setGravity(Gravity.CENTER);
        error.addView(message);
        Button retry = new Button(this); retry.setText("Tentar novamente");
        retry.setOnClickListener(v -> web.loadUrl(retryUrl)); error.addView(retry);
        Button home = new Button(this); home.setText("Voltar ao início");
        home.setOnClickListener(v -> web.loadUrl(HOME)); error.addView(home);
        content.addView(error, new FrameLayout.LayoutParams(-1,-1)); error.setVisibility(View.GONE);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                if (internal(r.getUrl())) return false;
                if (r.isForMainFrame()) external(r.getUrl());
                return true;
            }
            @Override public void onPageStarted(WebView v, String url, android.graphics.Bitmap icon) {
                failed = false; error.setVisibility(View.GONE); web.setVisibility(View.VISIBLE);
                progress.setVisibility(View.VISIBLE);
                if (internal(Uri.parse(url))) retryUrl = url;
            }
            @Override public void onPageFinished(WebView v, String url) {
                progress.setVisibility(View.GONE); CookieManager.getInstance().flush();
            }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) showError();
            }
            @Override public void onReceivedHttpError(WebView v, WebResourceRequest r, WebResourceResponse e) {
                if (r.isForMainFrame() && e.getStatusCode() >= 500) showError();
            }
            @Override public void onReceivedSslError(WebView v, SslErrorHandler handler, SslError e) {
                handler.cancel(); showError();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView v, int value) { progress.setProgress(value); }
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), PICK_FILE); }
                catch (ActivityNotFoundException e) { fileCallback.onReceiveValue(null); fileCallback = null; Toast.makeText(MainActivity.this,"Nenhum seletor de arquivos disponível",Toast.LENGTH_LONG).show(); }
                return true;
            }
        });
        web.setDownloadListener((url, agent, disposition, mime, size) -> external(Uri.parse(url)));
        if (state == null || web.restoreState(state) == null) web.loadUrl(HOME);
        if (Build.VERSION.SDK_INT >= 33) getOnBackInvokedDispatcher().registerOnBackInvokedCallback(0, this::goBack);
    }
    private boolean internal(Uri uri) {
        String path = uri.getPath();
        return "https".equals(uri.getScheme()) && "triade2-0.onrender.com".equals(uri.getHost())
            && (uri.getPort() == -1 || uri.getPort() == 443)
            && path != null && (path.equals("/kaka") || path.startsWith("/kaka/"));
    }
    private void external(Uri uri) {
        String scheme = uri.getScheme();
        if (!("https".equals(scheme) || "http".equals(scheme) || "tel".equals(scheme) || "mailto".equals(scheme) || "whatsapp".equals(scheme))) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)); }
        catch (ActivityNotFoundException e) { Toast.makeText(this,"Nenhum aplicativo disponível para abrir este link",Toast.LENGTH_LONG).show(); }
    }
    private void showError() { failed = true; web.setVisibility(View.INVISIBLE); error.setVisibility(View.VISIBLE); progress.setVisibility(View.GONE); }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private void goBack() {
        if (failed) { web.loadUrl(HOME); return; }
        if (web.canGoBack()) web.goBack(); else finish();
    }
    @Override public void onBackPressed() { goBack(); }
    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }
    @Override protected void onPause() { web.onPause(); CookieManager.getInstance().flush(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request,result,data);
        if (request == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data)); fileCallback = null;
        }
    }
    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        web.destroy(); super.onDestroy();
    }
}
