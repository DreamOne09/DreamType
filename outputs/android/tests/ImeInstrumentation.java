package tw.dreamtype.fixture;
import android.app.*;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.*;
import android.os.*;
import android.graphics.Bitmap;
import android.view.accessibility.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import java.io.*;

public final class ImeInstrumentation extends Instrumentation {
 @Override public void onCreate(Bundle args){super.onCreate(args);start();}
 private AccessibilityNodeInfo find(AccessibilityNodeInfo node,String text){
  if(node==null)return null;
  if(text.contentEquals(node.getText()==null?"":node.getText()))return node;
  for(int i=0;i<node.getChildCount();i++){AccessibilityNodeInfo found=find(node.getChild(i),text);if(found!=null)return found;}
  return null;
 }
 private AccessibilityNodeInfo find(String text){
  for(AccessibilityWindowInfo window:getUiAutomation().getWindows()){AccessibilityNodeInfo found=find(window.getRoot(),text);if(found!=null)return found;}
  return null;
 }
 private void screenshot(String name)throws Exception{
  Bitmap bitmap=getUiAutomation().takeScreenshot();if(bitmap==null)throw new AssertionError("No screenshot");
  try(FileOutputStream stream=new FileOutputStream(new File(getTargetContext().getExternalFilesDir(null),name+".png"))){bitmap.compress(Bitmap.CompressFormat.PNG,100,stream);}finally{bitmap.recycle();}
 }
 private void click(String label){
  long deadline=SystemClock.uptimeMillis()+20000;
  while(SystemClock.uptimeMillis()<deadline){
   AccessibilityNodeInfo node=find(label);
   if(node!=null&&node.isEnabled()&&node.performAction(AccessibilityNodeInfo.ACTION_CLICK))return;
   SystemClock.sleep(100);
  }
  throw new AssertionError("Cannot click: "+label);
 }
 private void recordAndInsert(Activity activity)throws Exception{
  click("開始說話");
  long deadline=SystemClock.uptimeMillis()+10000;
  while(find("停止並整理")==null&&SystemClock.uptimeMillis()<deadline)SystemClock.sleep(100);
  if(find("停止並整理")==null)throw new AssertionError("Recorder did not start");
  SystemClock.sleep(3000);screenshot("ime-recording");click("停止並整理");
  deadline=SystemClock.uptimeMillis()+20000;
  while(find("插入文字")==null&&SystemClock.uptimeMillis()<deadline)SystemClock.sleep(100);
  if(find("插入文字")==null)throw new AssertionError("No insertion preview after upload");
  screenshot("ime-preview");click("插入文字");
  final String[] value={""};deadline=SystemClock.uptimeMillis()+5000;
  do{runOnMainSync(()->value[0]=((EditText)activity.findViewById(101)).getText().toString());
   if("明天下午四點半到板橋。".equals(value[0])){screenshot("ime-inserted");return;}
   SystemClock.sleep(100);
  }while(SystemClock.uptimeMillis()<deadline);
  throw new AssertionError("External editor did not receive exact Traditional Chinese response");
 }
 private void check(Activity activity,int id,boolean enabled,String name)throws Exception{
  final boolean[] focused={false};long focusDeadline=SystemClock.uptimeMillis()+10000;
  do{runOnMainSync(()->focused[0]=activity.hasWindowFocus());if(focused[0])break;SystemClock.sleep(100);}while(SystemClock.uptimeMillis()<focusDeadline);
  if(!focused[0])throw new AssertionError("Editor window did not receive focus");
  runOnMainSync(()->{EditText field=activity.findViewById(id);field.requestFocus();((InputMethodManager)activity.getSystemService(Context.INPUT_METHOD_SERVICE)).showSoftInput(field,InputMethodManager.SHOW_IMPLICIT);});
  long deadline=SystemClock.uptimeMillis()+15000;
  while(SystemClock.uptimeMillis()<deadline){
   AccessibilityNodeInfo mic=find("開始說話");
   if(mic==null)runOnMainSync(()->{EditText field=activity.findViewById(id);((InputMethodManager)activity.getSystemService(Context.INPUT_METHOD_SERVICE)).showSoftInput(field,InputMethodManager.SHOW_IMPLICIT);});
   if(mic!=null&&mic.isEnabled()==enabled&&(enabled||find("密碼欄位不使用語音，請切回原本鍵盤。")!=null)){
    screenshot(name);return;
   }
   SystemClock.sleep(100);
  }
  throw new AssertionError("Microphone state mismatch: "+name);
 }
 @Override public void onStart(){Bundle result=new Bundle();
  try{
   AccessibilityServiceInfo info=getUiAutomation().getServiceInfo();info.flags|=AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;getUiAutomation().setServiceInfo(info);
   Activity activity=startActivitySync(new Intent(getTargetContext(),InputFixture.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();
   check(activity,101,true,"ime-normal");
   check(activity,102,false,"ime-password");
   check(activity,101,true,"ime-normal-return");
   recordAndInsert(activity);
   result.putString("ime","passed");result.putString("checks","external editor, real IME window, password disables voice, normal field restores voice");finish(Activity.RESULT_OK,result);
  }catch(Throwable error){try{screenshot("ime-failure");}catch(Exception ignored){}result.putString("ime","failed");result.putString("failure",error.toString());finish(Activity.RESULT_CANCELED,result);}
 }
}
