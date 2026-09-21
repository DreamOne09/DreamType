package tw.localvoice.keyboard;
import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.provider.Settings;
import android.view.*;
import android.view.inputmethod.*;
import android.widget.*;
import java.util.concurrent.*;

public final class HomeActivity extends Activity {
 private TextView state,detail;
 private Button action;
 private int step;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private TextView text(LinearLayout p,String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(Ui.INK);t.setPadding(0,dp(12),0,dp(8));p.addView(t);return t;}
 private Button button(LinearLayout p,String s,boolean primary,View.OnClickListener click){Button b=new Button(this);b.setText(s);b.setTextSize(17);Ui.button(b,primary);b.setOnClickListener(click);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(58));lp.setMargins(0,dp(8),0,dp(8));p.addView(b,lp);return b;}
 @Override public void onCreate(Bundle saved){super.onCreate(saved);
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Ui.PAPER);LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(28),dp(32),dp(28),dp(24));scroll.addView(p);setContentView(scroll);
  scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
  ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.voice_icon);logo.setContentDescription("DreamType");p.addView(logo,new LinearLayout.LayoutParams(dp(72),dp(72)));
  text(p,"DreamType",34);text(p,"自然說，\n清楚寫。",32);
  text(p,"說出想法，讓文字整理好。",17).setTextColor(Ui.MUTED);
  state=text(p,"",18);state.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
  detail=text(p,"",15);detail.setTextColor(Ui.MUTED);
  action=button(p,"開始使用",true,v->next());
  button(p,"我的設定",false,v->startActivity(new Intent(this,ManageActivity.class)));
  button(p,"帳號與連線",false,v->{PopupMenu menu=new PopupMenu(this,v);menu.getMenu().add("我的帳號");menu.getMenu().add("進階：私人電腦連線");menu.setOnMenuItemClickListener(item->{startActivity(new Intent(this,item.getTitle().toString().equals("我的帳號")?AccountActivity.class:SetupActivity.class));return true;});menu.show();});
  text(p,"只有按下錄音才會使用麥克風。文字由你確認後送出。",14).setTextColor(Ui.MUTED);
 }
 @Override protected void onResume(){super.onResume();refresh();}
 private void refresh(){
  action.setEnabled(true);
  if(!AppConfig.load(this).ready()){step=0;state.setText("第 1 步／共 3 步：登入");detail.setText("準備好管理者提供的服務網址與帳號，就能開始。");action.setText("登入開始使用");return;}
  if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){step=1;state.setText("第 2 步／共 3 步：麥克風");detail.setText("只有你按下錄音時才會使用。");action.setText("允許麥克風");return;}
  boolean enabled=false;for(InputMethodInfo i:((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).getEnabledInputMethodList())if(getPackageName().equals(i.getPackageName()))enabled=true;
  if(!enabled){step=2;state.setText("第 3 步／共 3 步：啟用鍵盤");detail.setText("原本的 Gboard 可以保留。");action.setText("啟用鍵盤");return;}
  step=3;state.setText("設定完成");detail.setText("開啟記事本或聊天輸入框，切換至 DreamType。");action.setText("切換到 DreamType");
 }
 private void next(){
  if(step==0)startActivity(new Intent(this,AccountActivity.class));
  else if(step==1)requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},1);
  else if(step==2)startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS));
  else{action.setEnabled(false);state.setText("確認電腦連線…");worker.execute(()->{String error=null;try{VoiceApi.verify(AppConfig.load(this));}catch(Exception e){error=VoiceApi.friendly(e);}final String problem=error;runOnUiThread(()->{if(isDestroyed()||isFinishing())return;action.setEnabled(true);if(problem!=null){state.setText("目前連不到電腦");detail.setText(problem);return;}state.setText("電腦已就緒");((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker();});});}
 }
 @Override public void onRequestPermissionsResult(int c,String[] p,int[] r){super.onRequestPermissionsResult(c,p,r);refresh();if(c==1&&(r.length==0||r[0]!=PackageManager.PERMISSION_GRANTED)){detail.setText("需要麥克風才能錄音。若無法再次詢問，請到系統 App 權限開啟。");}}
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
