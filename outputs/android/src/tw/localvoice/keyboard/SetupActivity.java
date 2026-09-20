package tw.localvoice.keyboard;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SetupActivity extends Activity {
    private EditText server,key;
    private TextView status;
    private CheckBox auto;
    private Button save;
    private LinearLayout connection;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private TextView text(LinearLayout parent,String value,int size) {
        TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Ui.INK);
        t.setPadding(0,dp(10),0,dp(8));parent.addView(t);return t;
    }
    private Button button(LinearLayout parent,String label,View.OnClickListener action) {
        Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(16);b.setOnClickListener(action);
        Ui.button(b,false);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(56));lp.setMargins(0,dp(4),0,dp(8));parent.addView(b,lp);return b;
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Ui.PAPER);
        LinearLayout column=new LinearLayout(this);column.setOrientation(LinearLayout.VERTICAL);column.setPadding(dp(22),dp(18),dp(22),dp(24));
        scroll.addView(column);setContentView(scroll);
        scroll.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        text(column,"連線設定",28);
        text(column,"把手機連到你的電腦。",17);
        status=text(column,AppConfig.load(this).ready()?"已儲存連線 · 電腦需保持開啟":"完成以下設定，就能開始說話",15);
        connection=new LinearLayout(this);connection.setOrientation(LinearLayout.VERTICAL);column.addView(connection);
        connection.setVisibility(View.VISIBLE);
        text(connection,"填入電腦提供的網址與金鑰，只需設定一次。也可從配對連結自動填入，日常使用不用開網頁。",15);
        text(connection,"電腦網址（HTTPS）",14);
        server=new EditText(this);server.setSingleLine(true);server.setTextSize(15);server.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);server.setHint("https://…trycloudflare.com");connection.addView(server);
        text(connection,"專用金鑰",14);
        key=new EditText(this);key.setSingleLine(true);key.setTextSize(15);key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);key.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);connection.addView(key);
        auto=new CheckBox(this);auto.setText("說完後自動放進原本輸入框");auto.setTextSize(16);connection.addView(auto);
        AppConfig config=AppConfig.load(this);server.setText(config.server);key.setText(config.accountMode?"":config.key);auto.setChecked(config.autoInsert);
        save=button(connection,"儲存並測試連線",v->saveAndTest());
        Ui.button(save,true);
        button(column,"返回首頁",v->{startActivity(new Intent(this,HomeActivity.class));finish();});
        text(column,"網址變更時只需更新這裡。電腦需保持開啟；錄音經你設定的 HTTPS 通道傳輸。",14);
        importPairing(getIntent());
    }
    @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);importPairing(intent);}
    private void importPairing(Intent intent) {
        Uri uri=intent.getData();if(uri==null||!"localvoice".equals(uri.getScheme())||!"pair".equals(uri.getHost()))return;
        try {
            String address=AppConfig.normalize(uri.getQueryParameter("server"));String token=uri.getQueryParameter("key");
            if(token==null||token.trim().isEmpty()||token.length()>512)throw new Exception("配對金鑰格式不正確。");
            connection.setVisibility(View.VISIBLE);server.setText(address);key.setText(token);status.setText("配對資料已填入。請確認網址，按「儲存並測試連線」。");
            // Imported links never silently replace an existing configuration.
            intent.setData(null);
        } catch(Exception e){status.setText("無法讀取配對連結，請手動填入網址與金鑰。");}
    }
    private void saveAndTest() {
        final AppConfig config;
        try {
            String token=key.getText().toString().trim();if(token.isEmpty()||token.length()>512)throw new Exception("請填入專用金鑰。");
            config=new AppConfig(AppConfig.normalize(server.getText().toString()),token,auto.isChecked());
        } catch(Exception e){status.setText(e.getMessage());return;}
        save.setEnabled(false);status.setText("正在連接你的電腦…");
        worker.execute(()->{
            String message;
            try {VoiceApi.verify(config);if(AppConfig.load(this).accountMode)AppConfig.clearSession(this);config.save(this);message="已儲存，電腦連線成功。返回首頁繼續設定。";}
            catch(Exception e){message=VoiceApi.friendly(e);}
            final String result=message;
            runOnUiThread(()->{if(!isFinishing()&&!isDestroyed()){status.setText(result);save.setEnabled(true);}});
        });
    }
    @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
