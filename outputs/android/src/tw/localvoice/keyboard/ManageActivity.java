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
  AppConfig config=AppConfig.load(this);
  text(p,"我的 DreamType",28);text(p,config.accountMode?"偏好儲存在你的帳號，可在其他裝置取回。":"設定只保存在這支手機；其他人的偏好不會被改動。",16);
  text(p,"說完之後",20);
  Spinner mode=new Spinner(this);mode.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"整理成台灣繁中","翻譯成其他語言"}));mode.setSelection(config.mode.equals("translate")?1:0);p.addView(mode,new LinearLayout.LayoutParams(-1,dp(48)));
  TextView targetLabel=new TextView(this);targetLabel.setText("翻譯成");targetLabel.setTextColor(Ui.INK);p.addView(targetLabel);
  Spinner target=new Spinner(this);target.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,AppConfig.LANGUAGE_NAMES));target.setSelection(AppConfig.languageIndex(config.targetLanguage));p.addView(target,new LinearLayout.LayoutParams(-1,dp(48)));
  target.setVisibility(mode.getSelectedItemPosition()==1?View.VISIBLE:View.GONE);targetLabel.setVisibility(target.getVisibility());
  mode.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> a){}public void onItemSelected(AdapterView<?> a,View v,int pos,long id){target.setVisibility(pos==1?View.VISIBLE:View.GONE);targetLabel.setVisibility(target.getVisibility());}});
  text(p,"我說的語言（預設中文）",16);
  String[] sourceNames=new String[9];sourceNames[0]="自動辨識";System.arraycopy(AppConfig.LANGUAGE_NAMES,0,sourceNames,1,8);
  Spinner source=new Spinner(this);source.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,sourceNames));source.setSelection(config.sourceLanguage.equals("auto")?0:AppConfig.languageIndex(config.sourceLanguage)+1);p.addView(source,new LinearLayout.LayoutParams(-1,dp(48)));
  text(p,"平常說中文即可；要說外文時再調整。翻譯不會替你回答問題或增加內容。",14);
  text(p,"我的整理提示詞",20);
  EditText prompt=field(p,"例如：使用台灣口語；工作安排用條列；保留所有時間與條件。",config.personalPrompt,2000);
  text(p,"最多 2,000 字。調整語氣和排版，不補寫沒說過的事。",14);
  text(p,"常用地名與人名",20);
  EditText words=field(p,"每行一個，例如：汐止、新莊、板橋、竹北、鹽埕、苓雅。也可以加入公司或人名。",config.vocabulary,1000);
  text(p,"最多 1,000 字。優先填最常用的詞；只作辨識參考，不強制替換同音字。",14);
  CheckBox taiwan=new CheckBox(this);taiwan.setText("加強台灣地名辨識");taiwan.setChecked(config.taiwanPlaces);p.addView(taiwan);
  CheckBox automatic=new CheckBox(this);automatic.setText("完成後直接插入（不先修改）");automatic.setChecked(config.autoInsert);p.addView(automatic);
  status=new TextView(this);status.setTextColor(Ui.MUTED);status.setTextSize(15);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);p.addView(status);
  Button save=button(p,"儲存我的偏好",v->{
   final String personal=prompt.getText().toString().trim(),vocabulary=words.getText().toString().trim();final boolean places=taiwan.isChecked(),auto=automatic.isChecked();
   final String outputMode=mode.getSelectedItemPosition()==1?"translate":"organize",targetCode=AppConfig.LANGUAGE_CODES[target.getSelectedItemPosition()],sourceCode=source.getSelectedItemPosition()==0?"auto":AppConfig.LANGUAGE_CODES[source.getSelectedItemPosition()-1];
   v.setEnabled(false);status.setText("正在儲存…");worker.execute(()->{String message;
    try{AppConfig active=AppConfig.load(this);if(!active.key.equals(config.key))throw new Exception("帳號已切換，請重新開啟設定。");
     org.json.JSONObject prefs=new org.json.JSONObject().put("personal_prompt",personal).put("vocabulary",vocabulary).put("taiwan_places",places).put("mode",outputMode).put("target_language",targetCode).put("source_language",sourceCode);
     if(active.accountMode)VoiceApi.json(active,"POST","/v2/me/preferences",prefs);
     AppConfig.saveStyle(this,prefs);getSharedPreferences("connection",MODE_PRIVATE).edit().putBoolean("auto",auto).commit();message="已儲存，下次錄音生效。";
    }catch(Exception e){message=VoiceApi.friendly(e);}final String result=message;runOnUiThread(()->{if(!isDestroyed()){status.setText(result);v.setEnabled(true);}});
   });
  });Ui.button(save,true);
  text(p,"連線與更新",20);
  text(p,"帳號模式：未完成錄音在手機加密保留一份，成功後刪除。超過一小時不可重試，下一次使用時清除過期檔案；登出亦清除。可在鍵盤「更多」手動刪除。",14);
  button(p,"測試電腦連線",v->{status.setText("正在測試…");v.setEnabled(false);worker.execute(()->{String result;try{VoiceApi.verify(AppConfig.load(this));result="電腦已連線。";}catch(Exception e){result=VoiceApi.friendly(e);}final String message=result;runOnUiThread(()->{if(!isDestroyed()){status.setText(message);v.setEnabled(true);}});});});
  button(p,config.accountMode?"帳號與本月用量":"修改電腦網址與金鑰",v->{startActivity(new Intent(this,config.accountMode?AccountActivity.class:SetupActivity.class));finish();});
  if(BuildChannel.PLAY_STORE){
   button(p,"在 Google Play 查看更新",v->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://play.google.com/store/apps/details?id="+getPackageName())));}catch(Exception e){status.setText("無法開啟 Google Play，請稍後再試。");}});
  }else{
  CheckBox previews=new CheckBox(this);previews.setText("更新時包含測試版（可能不穩定）");
  previews.setChecked(getSharedPreferences("updates",MODE_PRIVATE).getBoolean("previews",false));p.addView(previews);
  previews.setOnCheckedChangeListener((view,checked)->getSharedPreferences("updates",MODE_PRIVATE).edit().putBoolean("previews",checked).apply());
  button(p,"檢查 App 更新",v->{
   final boolean includePreviews=previews.isChecked();status.setText("正在檢查 GitHub…");v.setEnabled(false);previews.setEnabled(false);
   worker.execute(()->{UpdateCheck.Release release=null;try{release=UpdateCheck.latest(includePreviews);}catch(Exception ignored){}
    final UpdateCheck.Release found=release;
    runOnUiThread(()->{if(isDestroyed())return;v.setEnabled(true);previews.setEnabled(true);
     if(found==null){status.setText("暫時無法取得可安裝的更新，請稍後再試。");return;}
     try{
      String current=getPackageManager().getPackageInfo(getPackageName(),0).versionName;
      if(!UpdateCheck.newer(found.version,current)){status.setText("目前版本 "+current+"；"+(includePreviews?"穩定版與測試版":"穩定版")+"中沒有更高版本。");return;}
      new AlertDialog.Builder(this).setTitle("有新版 "+found.tag+(found.preview?"（測試版）":""))
       .setMessage("請先插入或取回上一筆文字，再下載 APK 安裝更新。不要解除安裝舊版。"+(found.preview?"\n測試版可能尚未完成手機驗收。":""))
       .setPositiveButton("開啟這個版本",(dialog,which)->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(found.url)));}catch(Exception error){status.setText("無法開啟瀏覽器，請到 DreamType 的 GitHub Releases 查看更新。");}})
       .setNegativeButton("稍後",null).show();
     }catch(Exception error){status.setText("無法讀取目前版本，請到 GitHub Releases 查看更新。");}
    });
   });
  });
  }
  try{text(p,"App 版本 "+getPackageManager().getPackageInfo(getPackageName(),0).versionName,14);}catch(Exception ignored){}
  button(p,"返回",v->finish());
 }
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
