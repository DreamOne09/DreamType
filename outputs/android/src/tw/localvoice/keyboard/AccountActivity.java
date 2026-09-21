package tw.localvoice.keyboard;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.util.concurrent.*;
import org.json.JSONObject;

/** Invitation-only beta account. Passwords are used once, never persisted. */
public final class AccountActivity extends Activity {
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private TextView status;
 private LinearLayout page;
 private boolean busy;
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private void text(String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextColor(Ui.INK);t.setTextSize(size);t.setPadding(0,dp(12),0,dp(8));page.addView(t);}
 private EditText field(String hint,String value,boolean password){
  text(hint,15);
  EditText e=new EditText(this);e.setText(value);e.setHint(hint);e.setTextSize(17);e.setSingleLine(true);
  e.setInputType(password?InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD:InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
  e.setContentDescription(hint);e.setSaveEnabled(false);e.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);page.addView(e,new LinearLayout.LayoutParams(-1,dp(60)));return e;
 }
 private Button button(String label,boolean primary,View.OnClickListener click){Button b=new Button(this);b.setText(label);Ui.button(b,primary);b.setOnClickListener(v->{if(!busy)click.onClick(v);});LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(56));lp.setMargins(0,dp(8),0,dp(8));page.addView(b,lp);return b;}
 private interface Action {String run() throws Exception;}
 private void task(Action action,boolean redraw){
  busy=true;status.setText("處理中…");
  worker.execute(()->{String result;boolean ok=false;try{result=action.run();ok=true;}catch(Exception e){result=VoiceApi.friendly(e);}final String message=result;final boolean success=ok;runOnUiThread(()->{if(isDestroyed())return;busy=false;if(success&&redraw)show();status.setText(message);});});
 }
 @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);show();}
 private void show(){
  ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Ui.PAPER);page=new LinearLayout(this);page.setOrientation(1);page.setPadding(dp(24),dp(20),dp(24),dp(24));scroll.addView(page);setContentView(scroll);
  scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
  text("我的帳號",28);AppConfig current=AppConfig.load(this);
  status=new TextView(this);status.setTextColor(Ui.MUTED);status.setTextSize(16);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
  if(current.ready()&&current.accountMode){
   text("封閉試用中 · 尚未收費",17);text("錄音由管理者的電腦處理。你的手機只需要網路。",15);page.addView(status);
   button("查看本月用量",true,v->task(()->{JSONObject me=VoiceApi.json(current,"GET","/v2/me",null);return "帳號："+me.getString("name")+"\n已用 "+Math.ceil(me.getDouble("used_seconds")/60)+" 分鐘／"+(me.getInt("limit_seconds")/60)+" 分鐘\n尚可使用約 "+(me.getInt("remaining_seconds")/60)+" 分鐘\n額度每月依 UTC 重算。";},false));
   button("同步我的偏好",false,v->task(()->{JSONObject me=VoiceApi.json(current,"GET","/v2/me",null);AppConfig.saveStyle(this,me.getJSONObject("preferences"));return "已取回帳號的提示詞與常用詞。";},false));
   button("修改密碼",false,v->{LinearLayout fields=new LinearLayout(this);fields.setOrientation(1);EditText oldPass=new EditText(this),newPass=new EditText(this);oldPass.setHint("目前密碼");newPass.setHint("新密碼（至少 12 字元）");for(EditText e:new EditText[]{oldPass,newPass}){e.setInputType(129);e.setSaveEnabled(false);e.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);fields.addView(e);}
    new AlertDialog.Builder(this).setTitle("修改密碼").setMessage("完成後，所有裝置都需要重新登入。").setView(fields).setPositiveButton("儲存",(d,w)->{final String oldValue=oldPass.getText().toString(),newValue=newPass.getText().toString();oldPass.setText("");newPass.setText("");task(()->{VoiceApi.json(current,"POST","/v2/me/password",new JSONObject().put("current_password",oldValue).put("new_password",newValue));AppConfig.clearSession(this);return "密碼已更新，請重新登入。";},true);}).setNegativeButton("取消",null).show();});
   button("登出",false,v->task(()->{VoiceApi.json(current,"POST","/v2/logout",new JSONObject());AppConfig.clearSession(this);return "已登出，手機上的帳號設定已清除。";},true));
   button("移除手機登入資料",false,v->new AlertDialog.Builder(this).setTitle("清除這支手機的登入？").setMessage("連不到服務時可使用。只清除手機資料，不會撤銷其他裝置的登入，也不會刪除帳號。")
     .setPositiveButton("清除",(d,w)->{AppConfig.clearSession(this);show();}).setNegativeButton("取消",null).show());
   button("刪除我的帳號",false,v->{EditText password=new EditText(this);password.setHint("再次輸入密碼");password.setInputType(129);password.setSaveEnabled(false);password.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
    new AlertDialog.Builder(this).setTitle("永久刪除帳號？").setMessage("帳號、所有登入、個人偏好與用量紀錄將刪除，無法復原。").setView(password).setPositiveButton("永久刪除",(d,w)->{final String pass=password.getText().toString();password.setText("");task(()->{VoiceApi.json(current,"DELETE","/v2/me",new JSONObject().put("password",pass));AppConfig.clearSession(this);return "帳號已刪除。";},true);}).setNegativeButton("取消",null).show();});
  }else{
   text("輸入管理者提供的網址與試用帳號。",16);
   EditText server=field("服務網址（https://…）",current.server,false);
   EditText username=field("帳號","",false),password=field("密碼","",true);page.addView(status);
   button("登入",true,v->{final String host=server.getText().toString(),name=username.getText().toString(),pass=password.getText().toString();password.setText("");
    task(()->{
     String normalized=AppConfig.normalize(host);
     JSONObject session=VoiceApi.json(new AppConfig(normalized,"",false),"POST","/v2/login",new JSONObject().put("username",name).put("password",pass));
     AppConfig config=new AppConfig(normalized,session.getString("token"),false,"","",true,true);
     JSONObject me=VoiceApi.json(config,"GET","/v2/me",null);
     AppConfig.clearSession(this);config.save(this);AppConfig.saveStyle(this,me.getJSONObject("preferences"));return "登入成功。回到首頁，繼續啟用鍵盤。";
    },true);
   });
   text("目前由管理者建立帳號，不開放自行註冊。登入有效七天，到期後重新登入。",14);
  }
  button("返回",false,v->finish());
 }
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
