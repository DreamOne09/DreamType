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

public final class HomeActivity extends Activity {
 private TextView state,detail;
 private Button action;
 private int step;
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private TextView text(LinearLayout p,String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(Ui.INK);t.setPadding(0,dp(12),0,dp(8));p.addView(t);return t;}
 private Button button(LinearLayout p,String s,boolean primary,View.OnClickListener click){Button b=new Button(this);b.setText(s);b.setTextSize(17);Ui.button(b,primary);b.setMinHeight(dp(58));b.setPadding(dp(16),dp(12),dp(16),dp(12));b.setOnClickListener(click);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,LinearLayout.LayoutParams.WRAP_CONTENT);lp.setMargins(0,dp(8),0,dp(8));p.addView(b,lp);return b;}
 @Override public void onCreate(Bundle saved){super.onCreate(saved);
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Ui.PAPER);LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(28),dp(32),dp(28),dp(24));scroll.addView(p);setContentView(scroll);
  scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
  ImageView logo=new ImageView(this);logo.setImageResource(R.drawable.voice_icon);logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);p.addView(logo,new LinearLayout.LayoutParams(dp(72),dp(72)));
  text(p,"DreamType",24);text(p,"自然說，清楚寫。",32);
  text(p,"說中文，自動整理成清楚的繁體文字。",17).setTextColor(Ui.MUTED);
  state=text(p,"",18);state.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
  detail=text(p,"",15);detail.setTextColor(Ui.MUTED);
  action=button(p,"開始使用",true,v->next());
  button(p,"設定與帳號",false,v->{
   PopupMenu menu=new PopupMenu(this,v);
   menu.getMenu().add(0,0,0,"我的用語與排版");
   menu.getMenu().add(0,1,1,"帳號與用量");
   menu.getMenu().add(0,2,2,"資料與隱私");
   menu.getMenu().add(0,3,3,"進階連線設定");
   menu.setOnMenuItemClickListener(item->{Class<?> page;
    switch(item.getItemId()){case 0:page=ManageActivity.class;break;case 1:page=AccountActivity.class;break;case 2:page=PrivacyActivity.class;break;default:page=SetupActivity.class;}
    startActivity(new Intent(this,page));return true;});menu.show();
  });
  text(p,"按下錄音才使用麥克風。預設先確認文字，再插入；可在設定開啟直接插入。",14).setTextColor(Ui.MUTED);
 }
 @Override protected void onResume(){super.onResume();refresh();}
 private void refresh(){
  action.setEnabled(true);
  if(!AppConfig.load(this).ready()){step=0;state.setText("第 1 步／共 3 步：登入");detail.setText("準備好管理者提供的服務網址與帳號，就能開始。");action.setText("登入開始使用");return;}
  if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){step=1;state.setText("第 2 步／共 3 步：麥克風");detail.setText("按下錄音才使用麥克風。錄音會透過網路傳到你設定的主機進行辨識與整理；詳見「資料與隱私」。");action.setText("允許麥克風");return;}
  boolean enabled=false;for(InputMethodInfo i:((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).getEnabledInputMethodList())if(getPackageName().equals(i.getPackageName()))enabled=true;
  if(!enabled){step=2;state.setText("第 3 步／共 3 步：啟用鍵盤");detail.setText("原本的 Gboard 可以保留。");action.setText("啟用鍵盤");return;}
  step=3;state.setText("準備好說話了");detail.setText("選擇 DreamType 鍵盤，再到 LINE 或記事本點一下輸入框，就能開始說話。");action.setText("選擇 DreamType 鍵盤");
 }
 private void next(){
  if(step==0)startActivity(new Intent(this,AccountActivity.class));
  else if(step==1)requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},1);
  else if(step==2)startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS));
  else ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker();
 }
 @Override public void onRequestPermissionsResult(int c,String[] p,int[] r){super.onRequestPermissionsResult(c,p,r);refresh();if(c==1&&(r.length==0||r[0]!=PackageManager.PERMISSION_GRANTED)){detail.setText("需要麥克風才能錄音。若無法再次詢問，請到系統 App 權限開啟。");}}
}
