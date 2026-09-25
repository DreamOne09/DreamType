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
  if(text.contentEquals(node.getText()==null?"":node.getText())||text.contentEquals(node.getContentDescription()==null?"":node.getContentDescription()))return node;
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
   if(node!=null&&node.isEnabled()){
    android.graphics.Rect r=new android.graphics.Rect();node.getBoundsInScreen(r);
    if(!r.isEmpty()){long down=SystemClock.uptimeMillis();touch(down,0,r.centerX(),r.centerY());touch(down,1,r.centerX(),r.centerY());return;}
   }
   SystemClock.sleep(100);
  }
  throw new AssertionError("Cannot click: "+label);
 }
 private android.graphics.Rect bounds(String label){AccessibilityNodeInfo node=find(label);if(node==null)throw new AssertionError("Missing "+label);android.graphics.Rect r=new android.graphics.Rect();node.getBoundsInScreen(r);return r;}
 private void touch(long down,int action,float x,float y){android.view.MotionEvent e=android.view.MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,x,y,0);e.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);getUiAutomation().injectInputEvent(e,true);e.recycle();}
 private String editorText(Activity activity){final String[] value={""};runOnMainSync(()->value[0]=((EditText)activity.findViewById(101)).getText().toString());return value[0];}
 private void setEditor(Activity activity,String text,int start,int end){runOnMainSync(()->{EditText f=activity.findViewById(101);f.setText(text);f.setSelection(start,end);});waitForIdleSync();SystemClock.sleep(750);}
 private void interactionChecks(Activity activity)throws Exception{
  setEditor(activity,"台灣測試",2,4);
  click("退格刪除");SystemClock.sleep(300);
  if(!"台灣".equals(editorText(activity)))throw new AssertionError("Backspace did not delete selection: "+editorText(activity));
  setEditor(activity,"台灣😀",4,4);
  click("退格刪除");SystemClock.sleep(300);
  if(!"台灣".equals(editorText(activity)))throw new AssertionError("Backspace split emoji: "+editorText(activity));
  setEditor(activity,"一二三四五六七八九十",10,10);
  android.graphics.Rect del=bounds("退格刪除");long down=SystemClock.uptimeMillis();touch(down,0,del.centerX(),del.centerY());SystemClock.sleep(700);touch(down,1,del.centerX(),del.centerY());SystemClock.sleep(200);
  int remaining=editorText(activity).length();if(remaining>=9||remaining==0)throw new AssertionError("Hold backspace failed: "+remaining);
  setEditor(activity,"",0,0);
  android.graphics.Rect mic=bounds("開始說話");if(Math.abs(mic.width()-mic.height())>3)throw new AssertionError("Speak button not circular");
  down=SystemClock.uptimeMillis();touch(down,0,mic.centerX(),mic.centerY());
  long menuDeadline=SystemClock.uptimeMillis()+5000;while(find("翻譯成英文")==null&&SystemClock.uptimeMillis()<menuDeadline)SystemClock.sleep(100);
  android.graphics.Rect english=bounds("翻譯成英文");screenshot("ime-translation-menu");
  touch(down,2,english.centerX(),english.centerY());SystemClock.sleep(200);touch(down,1,english.centerX(),english.centerY());SystemClock.sleep(500);
  if(find("停止並翻譯")==null)throw new AssertionError("Slide selection did not start translated recording");
  check(activity,102,false,"ime-translation-cancel");check(activity,101,true,"ime-translation-return");
  click("翻譯 → 英文 ▾");click("整理成台灣繁中");
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
   if("明天下午四點半到板橋。".equals(value[0])){waitForIdleSync();SystemClock.sleep(750);screenshot("ime-inserted");
    click("復原剛才輸入");SystemClock.sleep(500);
    if(!"".equals(editorText(activity)))throw new AssertionError("Undo did not remove exact insertion");
    setEditor(activity,"原文",0,2);
    click("插入文字");SystemClock.sleep(500);
    if(!"明天下午四點半到板橋。".equals(editorText(activity)))throw new AssertionError("Undo lost pending result");
    click("復原剛才輸入");SystemClock.sleep(500);
    if(!"原文".equals(editorText(activity)))throw new AssertionError("Undo lost replaced selection");
    setEditor(activity,"",0,0);
    click("插入文字");SystemClock.sleep(500);
    setEditor(activity,"明天下午四點半到板橋。補充",13,13);
    if(find("復原剛才輸入")!=null)click("復原剛才輸入");SystemClock.sleep(300);
    if(!"明天下午四點半到板橋。補充".equals(editorText(activity)))throw new AssertionError("Undo changed edited text");
    return;}
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
   interactionChecks(activity);
   recordAndInsert(activity);
   result.putString("ime","passed");result.putString("checks","circle, selection and emoji backspace, hold delete, long press slide translation, external editor, real IME window, password disables voice, normal field restores voice, MediaRecorder upload, fixed Traditional Chinese response inserted");finish(Activity.RESULT_OK,result);
  }catch(Throwable error){try{screenshot("ime-failure");}catch(Exception ignored){}result.putString("ime","failed");result.putString("failure",error.toString());finish(Activity.RESULT_CANCELED,result);}
 }
}
