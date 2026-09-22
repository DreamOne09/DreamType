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
 @Override public void onCreate(Bundle args){super.onCreate(args);configureVoice=args!=null&&"true".equals(args.getString("configure_voice"));accountVoice=args!=null&&"true".equals(args.getString("account_voice"));verifyDelivered=args!=null&&"true".equals(args.getString("verify_delivered"));start();}
 private TextView find(View v,String text){
  if(v instanceof TextView&&text.equals(((TextView)v).getText().toString()))return (TextView)v;
  if(v instanceof ViewGroup){ViewGroup group=(ViewGroup)v;for(int i=0;i<group.getChildCount();i++){TextView result=find(group.getChildAt(i),text);if(result!=null)return result;}}
  return null;
 }
 private Activity open(Class<?> page){Activity a=startActivitySync(new Intent(getTargetContext(),page).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();return a;}
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
   if(configureVoice)new AppConfig("http://10.0.2.2:18765","synthetic-emulator-token",false,"","",true,accountVoice).save(context);
   result.putString("dreamtype","passed");result.putString("checks","Chinese onboarding, login navigation, Android Keystore credentials and recording, logout deletion, offline privacy");
   finish(Activity.RESULT_OK,result);
  }catch(Throwable failure){result.putString("dreamtype","failed");result.putString("failure",failure.toString());finish(Activity.RESULT_CANCELED,result);}
 }
}
