package tw.localvoice.keyboard;

import android.app.*;
import android.os.*;
import android.content.*;
import android.net.Uri;
import android.view.*;
import android.widget.*;
import androidx.credentials.*;
import androidx.credentials.exceptions.*;
import com.google.android.libraries.identity.googleid.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Explicit user-initiated Google account flow. Tokens stay in memory. */
public final class GoogleAccountActivity extends Activity {
 private static final String ORIGIN="https://dreamtype.dreamone.li";
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private final List<Button> actions=new ArrayList<>();
 private final CancellationSignal cancellation=new CancellationSignal();
 private AppConfig expected,publicConfig;
 private TextView status;
 private LinearLayout page;
 private String clientId;
 private boolean busy;
 private volatile boolean destroyed;
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private boolean current(){return !destroyed&&!isFinishing()&&expected.sameSession(AppConfig.load(this));}
 private void label(String text,int size){TextView t=new TextView(this);t.setText(text);t.setTextColor(Ui.INK);t.setTextSize(size);t.setPadding(0,dp(12),0,dp(12));page.addView(t);}
 private void button(String text,boolean primary,Runnable run){Button b=new Button(this);b.setText(text);Ui.button(b,primary);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(56));p.setMargins(0,dp(8),0,dp(8));page.addView(b,p);actions.add(b);b.setOnClickListener(v->{if(!busy&&current())run.run();});}
 private void state(boolean working,String text){runOnUiThread(()->{if(destroyed)return;busy=working;for(Button b:actions)b.setEnabled(!working);status.setText(text);});}
 @Override public void onCreate(Bundle saved){
  super.onCreate(saved);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
  expected=AppConfig.load(this);publicConfig=new AppConfig(ORIGIN,"",false);
  ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Ui.PAPER);page=new LinearLayout(this);page.setOrientation(LinearLayout.VERTICAL);page.setPadding(dp(24),dp(20),dp(24),dp(24));scroll.addView(page);setContentView(scroll);
  scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
  label("Google 帳號",28);label("在不同裝置使用同一個 DreamType 帳號。",16);
  status=new TextView(this);status.setTextSize(16);status.setTextColor(Ui.MUTED);status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);status.setText("正在確認登入服務…");page.addView(status);
  Button back=new Button(this);back.setText("返回");Ui.button(back,false);page.addView(back,new LinearLayout.LayoutParams(-1,dp(56)));back.setOnClickListener(v->finish());
  worker.execute(()->{try{
   JSONObject config=VoiceApi.json(publicConfig,"GET","/v2/auth/google/config",null);
   String id=config.getString("client_id");if(!id.matches("[A-Za-z0-9_-]+\\.apps\\.googleusercontent\\.com"))throw new Exception();
   boolean google=false;
   if(expected.ready()&&expected.accountMode&&ORIGIN.equals(expected.server)){
    JSONArray methods=VoiceApi.json(expected,"GET","/v2/me",null).optJSONArray("login_methods");
    if(methods!=null)for(int i=0;i<methods.length();i++)if("google".equals(methods.optString(i)))google=true;
   }
   final boolean linked=google;runOnUiThread(()->{if(!current())return;clientId=id;
    if(linked){label("已連結 Google 帳號",18);button("管理 Google Play 訂閱",false,()->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://play.google.com/store/account/subscriptions")));}catch(Exception e){state(false,"無法開啟訂閱頁，請從 Google Play 管理訂閱。");}});button("刪除我的帳號",false,this::confirmDelete);}
    else {button("使用 Google 登入",true,()->confirmLogin("signin"));if(config.optBoolean("signup_enabled",false))button("使用 Google 建立帳號",false,()->confirmLogin("signup"));label("已有試用帳號請返回使用原帳號登入，兩種帳號不會自動合併。",16);}
    state(false,"請選擇要進行的操作。");
   });
  }catch(Exception e){state(false,"Google 登入目前尚未開放或暫時無法連線。請返回使用原本的帳號登入。");}});
 }
 private void confirmLogin(String purpose){
  String message="signup".equals(purpose)?"將建立新的 DreamType 帳號，不會自動訂閱或扣款。":"請選擇原本使用的 Google 帳號。";
  if(expected.ready())message+="\n登入成功後會替換手機目前的登入，並清除舊登入的未完成錄音。需要保留錄音時，請先返回鍵盤處理。";
  new AlertDialog.Builder(this).setTitle("signup".equals(purpose)?"建立 DreamType 帳號":"使用 Google 登入").setMessage(message).setPositiveButton("繼續",(d,w)->begin(purpose)).setNegativeButton("取消",null).show();
 }
 private void confirmDelete(){new AlertDialog.Builder(this).setTitle("永久刪除 DreamType 帳號？").setMessage("帳號、登入、偏好及用量將刪除，無法復原。主機保留刪除紀錄，避免舊備份復活帳號。\n\n這不會取消 Google Play 訂閱，也不會自動退款。請先使用「管理 Google Play 訂閱」確認。\n\n接著需重新驗證同一個 Google 帳號。").setPositiveButton("重新驗證並刪除",(d,w)->begin("delete")).setNegativeButton("取消",null).show();}
 private void begin(String purpose){
  if(!current()||busy)return;state(true,"正在準備 Google 身分確認…");
  worker.execute(()->{try{
   if(!current())return;
   boolean deleting="delete".equals(purpose);
   if(deleting&&!ORIGIN.equals(expected.server))throw new Exception();
   JSONObject c=VoiceApi.json(deleting?expected:publicConfig,"POST",deleting?"/v2/me/google/delete/challenge":"/v2/auth/google/challenge",deleting?new JSONObject():new JSONObject().put("purpose",purpose));
   String nonce=c.getString("nonce");if(!nonce.matches("[A-Za-z0-9_-]{43}")||!c.getString("challenge").matches("[0-9a-f]{32}")||!c.getString("secret").matches("[A-Za-z0-9_-]{43}"))throw new Exception();
   runOnUiThread(()->{if(!current())return;
    try{GetCredentialRequest request=new GetCredentialRequest.Builder().addCredentialOption(new GetSignInWithGoogleOption.Builder(clientId).setNonce(nonce).build()).build();
    CredentialManager.create(this).getCredentialAsync(new MutableContextWrapper(this),request,cancellation,this::runOnUiThread,new CredentialManagerCallback<GetCredentialResponse,GetCredentialException>(){
     public void onResult(GetCredentialResponse response){if(!current())return;try{
      Credential credential=response.getCredential();
      if(!(credential instanceof CustomCredential)||!GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType()))throw new Exception();
      String token=GoogleIdTokenCredential.createFrom(credential.getData()).getIdToken();complete(purpose,c,token);
     }catch(Exception e){state(false,"無法確認 Google 身分，請重新開始。");}}
     public void onError(GetCredentialException e){if(current())state(false,e instanceof GetCredentialCancellationException?"已取消，沒有更動帳號。":"Google 身分確認未完成，請稍後重試。");}
    });}catch(Exception e){state(false,"Google 身分服務無法開啟，請稍後重試。");}
   });
  }catch(Exception e){state(false,"無法開始身分確認，請稍後重試。");}});
 }
 private void complete(String purpose,JSONObject challenge,String token){
  state(true,"正在由 DreamType 確認身分…");
  worker.execute(()->{try{
   if(!current())return;
   JSONObject body=new JSONObject().put("challenge",challenge.getString("challenge")).put("secret",challenge.getString("secret")).put("id_token",token);
   if("delete".equals(purpose)){
    body.put("confirm",true);JSONObject result=VoiceApi.json(expected,"POST","/v2/me/google/delete/complete",body);
    if(!result.optBoolean("deleted",false))throw new Exception();
    AppConfig.clearSessionIfCurrent(this,expected);clearProviderState(this);
    runOnUiThread(()->{if(!destroyed){Toast.makeText(this,"帳號已刪除；Google Play 訂閱請另外確認。",Toast.LENGTH_LONG).show();finish();}});
   }else{
    JSONObject result=VoiceApi.json(publicConfig,"POST","/v2/auth/google/complete",body);
    AppConfig next=new AppConfig(ORIGIN,result.getString("token"),false,"","",true,true);
    try {if(!current())throw new Exception();JSONObject me=VoiceApi.json(next,"GET","/v2/me",null);if(!current())throw new Exception();AppConfig.replaceSession(this,expected,next,me.getJSONObject("preferences"));}
    catch(Exception e){try{VoiceApi.json(next,"POST","/v2/logout",new JSONObject());}catch(Exception ignored){}throw e;}
    runOnUiThread(()->{if(!destroyed){Toast.makeText(this,"登入成功，請返回鍵盤使用。",Toast.LENGTH_LONG).show();finish();}});
   }
  }catch(Exception e){state(false,"操作尚未確認，請重新登入確認帳號狀態。未完成的刪除請勿當成已成功。");}});
 }
 public static void clearProviderState(Context context){
  CredentialManager.create(context.getApplicationContext()).clearCredentialStateAsync(new ClearCredentialStateRequest(),null,Runnable::run,new CredentialManagerCallback<Void,ClearCredentialException>(){public void onResult(Void value){}public void onError(ClearCredentialException error){}});
 }
 @Override protected void onResume(){super.onResume();if(expected!=null&&!expected.sameSession(AppConfig.load(this)))finish();}
 @Override protected void onDestroy(){destroyed=true;cancellation.cancel();worker.shutdownNow();super.onDestroy();}
}
