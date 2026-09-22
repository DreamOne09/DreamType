package tw.localvoice.keyboard;
import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.nio.file.Files;
import java.util.Arrays;

/** Included only in the disposable emulator APK, never in a release build. */
public final class SmokeInstrumentation extends Instrumentation {
 private boolean configureVoice,accountVoice,verifyDelivered;
 private String voiceToken="synthetic-emulator-token";
 @Override public void onCreate(Bundle args){super.onCreate(args);configureVoice=args!=null&&"true".equals(args.getString("configure_voice"));accountVoice=args!=null&&"true".equals(args.getString("account_voice"));verifyDelivered=args!=null&&"true".equals(args.getString("verify_delivered"));if(args!=null)voiceToken=args.getString("voice_token",voiceToken);start();}
 private TextView find(View v,String text){
  if(v instanceof TextView&&text.equals(((TextView)v).getText().toString()))return (TextView)v;
  if(v instanceof ViewGroup){ViewGroup group=(ViewGroup)v;for(int i=0;i<group.getChildCount();i++){TextView result=find(group.getChildAt(i),text);if(result!=null)return result;}}
  return null;
 }
 private Activity open(Class<?> page){Activity a=startActivitySync(new Intent(getTargetContext(),page).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();return a;}
 private interface LateAction {void run()throws Exception;}
 private void rejected(LateAction action)throws Exception {
  try{action.run();throw new AssertionError("Stale session write accepted");}catch(java.io.IOException expected){}
 }
 private void sessionChecks(Context context)throws Exception {
  AppConfig first=new AppConfig("https://first.invalid","synthetic-first",false,"","",true,true);
  AppConfig second=new AppConfig("https://second.invalid","synthetic-second",false,"","",true,true);
  org.json.JSONObject oldPrefs=new org.json.JSONObject().put("personal_prompt","舊帳號偏好");
  org.json.JSONObject newPrefs=new org.json.JSONObject().put("personal_prompt","新帳號偏好");
  first.save(context);AppConfig.replaceSession(context,first,second,newPrefs);
  rejected(()->AppConfig.savePreferences(context,first,oldPrefs,true));
  rejected(()->AppConfig.clearSessionIfCurrent(context,first));
  rejected(()->AppConfig.replaceSession(context,first,first,oldPrefs));
  rejected(()->AppConfig.saveConnection(context,first,first));
  AppConfig current=AppConfig.load(context);
  if(!current.key.equals(second.key)||!current.personalPrompt.equals("新帳號偏好")||current.autoInsert)throw new AssertionError("New account changed by stale reply");
  AppConfig differentHost=new AppConfig("https://other.invalid",second.key,false,"","",true,true);
  rejected(()->AppConfig.savePreferences(context,differentHost,oldPrefs,true));
  AppConfig.savePreferences(context,second,new org.json.JSONObject().put("personal_prompt","目前帳號偏好"),true);
  current=AppConfig.load(context);
  if(!current.autoInsert||!current.personalPrompt.equals("目前帳號偏好"))throw new AssertionError("Current account preference write failed");
  AppConfig.clearSessionIfCurrent(context,second);
  if(!AppConfig.load(context).key.isEmpty())throw new AssertionError("Current account logout failed");
 }
 private EditText input(View view){
  if(view instanceof EditText)return (EditText)view;
  if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){EditText found=input(((ViewGroup)view).getChildAt(i));if(found!=null)return found;}
  return null;
 }
 private void editorChecks(Context context)throws Exception{
  new AppConfig("https://example.invalid","synthetic-editor-token",false).save(context);
  Draft.begin("明天到板橋。");Activity first=open(EditActivity.class);
  runOnMainSync(()->{EditText field=input(first.getWindow().getDecorView());field.setText("明天下午到汐止。");field.setSelection(2,4);});
  ActivityMonitor monitor=addMonitor(EditActivity.class.getName(),null,false);
  runOnMainSync(()->first.recreate());Activity recreated=waitForMonitorWithTimeout(monitor,5000);removeMonitor(monitor);
  if(recreated==null)throw new AssertionError("Editor did not recreate");waitForIdleSync();
  runOnMainSync(()->{
   EditText field=input(recreated.getWindow().getDecorView());
   if(!"明天下午到汐止。".equals(field.getText().toString())||field.getSelectionStart()!=2||field.getSelectionEnd()!=4)throw new AssertionError("Unsaved edit or selection lost on recreation");
   if(field.isSaveEnabled())throw new AssertionError("Editor text may enter saved instance state");
   find(recreated.getWindow().getDecorView(),"復原這次修改").performClick();
   if(!"明天到板橋。".equals(field.getText().toString()))throw new AssertionError("Restore lost original text");
   field.setText("明天下午到汐止。");
  });
  screenshot("editor-recreated");runOnMainSync(()->find(recreated.getWindow().getDecorView(),"完成修改").performClick());waitForIdleSync();
  if(!Draft.edited||!"明天下午到汐止。".equals(Draft.text))throw new AssertionError("Edited handoff missing");
  Draft.begin("舊的文字。");Activity stale=open(EditActivity.class);
  runOnMainSync(()->{Draft.begin("新的文字。");find(stale.getWindow().getDecorView(),"完成修改").performClick();});waitForIdleSync();
  if(Draft.edited||!"新的文字。".equals(Draft.text))throw new AssertionError("Old editor overwrote new draft");
  Activity logout=open(EditActivity.class);AppConfig.clearSession(context);
  runOnMainSync(()->find(logout.getWindow().getDecorView(),"完成修改").performClick());waitForIdleSync();
  if(Draft.text!=null||Draft.edited)throw new AssertionError("Editor restored text after logout");
 }
 private void screenshot(String name)throws Exception{
  // System bar transitions do not necessarily post accessibility idle events.
  android.os.SystemClock.sleep(2000);
  getUiAutomation().waitForIdle(750,5000);
  Bitmap image=getUiAutomation().takeScreenshot();if(image==null)throw new AssertionError("Screenshot unavailable");
  try(FileOutputStream stream=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),name+".png"))){image.compress(Bitmap.CompressFormat.PNG,100,stream);}finally{image.recycle();}
 }
 @Override public void onStart(){
  Bundle result=new Bundle();
  try{
   Context context=getTargetContext();
   if(verifyDelivered){
    if(!AppConfig.load(context).accountMode)throw new AssertionError("Account mode was not used");
    if(new File(context.getNoBackupFilesDir(),"pending-recording.bin").exists())throw new AssertionError("Delivered recording still retained");
    if(new File(context.getNoBackupFilesDir(),"pending-recording.bin.tmp").exists())throw new AssertionError("Temporary recording still retained");
    result.putString("delivered","passed");finish(Activity.RESULT_OK,result);return;
   }
   AppConfig.clearSession(context);
   Activity home=open(HomeActivity.class);
   final TextView[] login={null};runOnMainSync(()->{login[0]=find(home.getWindow().getDecorView(),"登入開始使用");});
   if(!(login[0] instanceof Button))throw new AssertionError("Traditional Chinese onboarding button missing");
   runOnMainSync(()->{
    int appearance=home.getWindow().getInsetsController().getSystemBarsAppearance();
    if((appearance&WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS)==0)throw new AssertionError("Status bar icons are not dark on the light home screen");
   });
   screenshot("home");
   ActivityMonitor monitor=addMonitor(AccountActivity.class.getName(),null,false);
   runOnMainSync(()->login[0].performClick());
   Activity account=waitForMonitorWithTimeout(monitor,5000);removeMonitor(monitor);
   if(account==null)throw new AssertionError("Login navigation failed");
   runOnMainSync(()->account.finish());waitForIdleSync();
   AppConfig config=new AppConfig("https://example.invalid","synthetic-emulator-token",false,"","",true,true,"translate","ja","zh-TW");
   config.save(context);
   if(!AppConfig.load(context).key.equals(config.key))throw new AssertionError("Android Keystore credential roundtrip failed");
   if(context.getSharedPreferences("connection",0).getAll().toString().contains(config.key))throw new AssertionError("Token stored unencrypted");
   File audio=new File(context.getCacheDir(),"synthetic.bin");byte[] sample={1,2,3,4};Files.write(audio.toPath(),sample);
   EncryptedRecording.Entry entry=PendingAudio.prepare(context,config,audio);
   EncryptedRecording.Entry recovered=PendingAudio.read(context,config);
   if(!entry.id.equals(recovered.id)||!Arrays.equals(sample,recovered.audio)||!"ja".equals(recovered.target))throw new AssertionError("Keystore recording roundtrip failed");
   File stored=new File(context.getNoBackupFilesDir(),"pending-recording.bin");
   if(!stored.isFile())throw new AssertionError("Recording missing before logout");
   audio.delete();AppConfig.clearSession(context);
   // Inspect the file directly: available()/exists() can itself delete old files.
   if(stored.exists()||new File(stored.getPath()+".tmp").exists())throw new AssertionError("Logout did not clear pending audio");
   if(!AppConfig.load(context).key.isEmpty())throw new AssertionError("Logout did not clear credential");
   Activity privacy=open(PrivacyActivity.class);
   final boolean[] found={false};runOnMainSync(()->{found[0]=find(privacy.getWindow().getDecorView(),"資料與隱私")!=null;});
   if(!found[0])throw new AssertionError("Offline privacy screen missing");
   screenshot("privacy");
   editorChecks(context);
   sessionChecks(context);result.putString("session_isolation","passed");
   if(configureVoice)new AppConfig("http://10.0.2.2:18765",voiceToken,false,"","",true,accountVoice).save(context);
   result.putString("dreamtype","passed");result.putString("checks","Chinese onboarding, login navigation, Android Keystore credentials and recording, logout deletion, offline privacy");
   finish(Activity.RESULT_OK,result);
  }catch(Throwable failure){result.putString("dreamtype","failed");result.putString("failure",failure.toString());finish(Activity.RESULT_CANCELED,result);}
 }
}
