package tw.localvoice.keyboard;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputFilter;
import android.view.*;
import android.widget.*;
import java.util.concurrent.*;

public final class ManageActivity extends Activity {
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private TextView status;
 private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
 private void text(LinearLayout p,String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextColor(Ui.INK);t.setTextSize(size);t.setPadding(0,dp(12),0,dp(8));p.addView(t);}
 private Button button(LinearLayout p,String s,View.OnClickListener action){Button b=new Button(this);b.setText(s);Ui.button(b,false);b.setOnClickListener(action);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(56));lp.setMargins(0,dp(8),0,dp(8));p.addView(b,lp);return b;}
 private EditText field(LinearLayout p,String hint,String value,int max){EditText e=new EditText(this);e.setTextSize(16);e.setText(value);e.setHint(hint);e.setMinLines(3);e.setGravity(Gravity.TOP);e.setFilters(new InputFilter[]{new InputFilter.LengthFilter(max)});e.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);p.addView(e);return e;}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Ui.PAPER);LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(24),dp(16),dp(24),dp(24));scroll.addView(p);setContentView(scroll);
  scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
  text(p,"我的 DreamType",28);text(p,"設定只保存在這支手機；其他人的偏好不會被改動。",16);
  AppConfig config=AppConfig.load(this);
  text(p,"我的整理提示詞",20);
  EditText prompt=field(p,"例如：使用台灣口語；工作安排用條列；保留所有時間與條件。",config.personalPrompt,2000);
  text(p,"最多 2,000 字。調整語氣和排版，不補寫沒說過的事。",14);
  text(p,"常用地名與人名",20);
  EditText words=field(p,"每行一個，例如：汐止、新莊、板橋、竹北、鹽埕、苓雅。也可以加入公司或人名。",config.vocabulary,1000);
  text(p,"最多 1,000 字。優先填最常用的詞；只作辨識參考，不強制替換同音字。",14);
  CheckBox taiwan=new CheckBox(this);taiwan.setText("加強台灣地名辨識");taiwan.setChecked(config.taiwanPlaces);p.addView(taiwan);
  CheckBox automatic=new CheckBox(this);automatic.setText("整理完成後直接插入（不先修改）");automatic.setChecked(config.autoInsert);p.addView(automatic);
  status=new TextView(this);status.setTextColor(Ui.MUTED);status.setTextSize(15);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);p.addView(status);
  Button save=button(p,"儲存我的偏好",v->{
   getSharedPreferences("style",MODE_PRIVATE).edit().putString("prompt",prompt.getText().toString().trim()).putString("vocabulary",words.getText().toString().trim()).putBoolean("taiwan",taiwan.isChecked()).apply();
   getSharedPreferences("connection",MODE_PRIVATE).edit().putBoolean("auto",automatic.isChecked()).apply();
   status.setText("已儲存，下次錄音生效。");
  });Ui.button(save,true);
  text(p,"連線與更新",20);
  button(p,"測試電腦連線",v->{status.setText("正在測試…");v.setEnabled(false);worker.execute(()->{String result;try{VoiceApi.verify(AppConfig.load(this));result="電腦已連線。";}catch(Exception e){result=VoiceApi.friendly(e);}final String message=result;runOnUiThread(()->{if(!isDestroyed()){status.setText(message);v.setEnabled(true);}});});});
  button(p,"修改電腦網址與金鑰",v->{startActivity(new Intent(this,SetupActivity.class));finish();});
  button(p,"檢查 App 更新",v->{status.setText("正在檢查 GitHub…");v.setEnabled(false);worker.execute(()->{String tag=null,problem=null;try{tag=UpdateCheck.latest();}catch(Exception e){problem="暫時無法檢查更新，請稍後再試。";}final String version=tag,error=problem;runOnUiThread(()->{if(isDestroyed())return;v.setEnabled(true);if(error!=null){status.setText(error);return;}try{String current=getPackageManager().getPackageInfo(getPackageName(),0).versionName;if(!UpdateCheck.newer(version,current)){status.setText("目前已是最新版本 "+current);return;}new AlertDialog.Builder(this).setTitle("有新版 "+version).setMessage("開啟 GitHub 下載 APK，安裝時選擇更新。已儲存設定會保留。").setPositiveButton("開啟下載",(d,w)->startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://github.com/DreamOne09/DreamType/releases/latest")))).setNegativeButton("稍後",null).show();}catch(Exception e){status.setText("請到 GitHub Releases 查看更新。");}});});});
  try{text(p,"App 版本 "+getPackageManager().getPackageInfo(getPackageName(),0).versionName,14);}catch(Exception ignored){}
  button(p,"返回",v->finish());
 }
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
