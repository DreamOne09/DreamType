package tw.localvoice.keyboard;
import android.app.Activity;
import android.os.Bundle;
import android.content.*;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

public final class EditActivity extends Activity {
 private EditText editor;
 private String original,sessionKey;
 private long draftRevision;
 private static final class EditorState {
  final String original,text,key;final int start,end;final long revision;
  EditorState(String original,String text,String key,int start,int end,long revision){this.original=original;this.text=text;this.key=key;this.start=start;this.end=end;this.revision=revision;}
 }
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private Button button(LinearLayout p,String label,View.OnClickListener action){Button b=new Button(this);b.setText(label);Ui.button(b,false);b.setOnClickListener(action);p.addView(b,new LinearLayout.LayoutParams(-1,dp(52)));return b;}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  if(Draft.text==null){Toast.makeText(this,"暫存文字已清除，請重新錄音。",Toast.LENGTH_LONG).show();finish();return;}
  EditorState retained=(EditorState)getLastNonConfigurationInstance();
  original=retained==null?Draft.text:retained.original;
  sessionKey=retained==null?AppConfig.load(this).key:retained.key;
  draftRevision=retained==null?Draft.revision:retained.revision;
  LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(20),dp(16),dp(20),dp(16));p.setBackgroundColor(Ui.PAPER);setContentView(p);
  p.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(dp(20)+i.getSystemWindowInsetLeft(),dp(16)+i.getSystemWindowInsetTop(),dp(20)+i.getSystemWindowInsetRight(),dp(16)+i.getSystemWindowInsetBottom());return i;});
  TextView title=new TextView(this);title.setText("修改文字");title.setTextColor(Ui.INK);title.setTextSize(24);p.addView(title);
  TextView hint=new TextView(this);hint.setText("可切換 Gboard 修改。完成後回到原 App，切回 DreamType，再按「插入」。");hint.setTextColor(Ui.MUTED);hint.setTextSize(15);p.addView(hint);
  editor=new EditText(this);editor.setText(retained==null?original:retained.text);editor.setTextColor(Ui.INK);editor.setTextSize(18);editor.setGravity(Gravity.TOP);editor.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);editor.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);editor.setSaveEnabled(false);editor.setContentDescription("要修改的文字");p.addView(editor,new LinearLayout.LayoutParams(-1,0,1));
  if(retained!=null)editor.setSelection(Math.max(0,Math.min(retained.start,editor.length())),Math.max(0,Math.min(retained.end,editor.length())));
  button(p,"切換打字鍵盤",v->((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker());
  LinearLayout restoreRow=new LinearLayout(this);p.addView(restoreRow);
  Button restoreEdit=button(restoreRow,"復原這次修改",v->editor.setText(original));restoreEdit.setLayoutParams(new LinearLayout.LayoutParams(0,dp(52),1));
  if(Draft.rawText!=null&&!Draft.rawText.isEmpty()){Button restoreRaw=button(restoreRow,"還原辨識原文",v->{
   if(draftRevision==Draft.revision&&sessionKey.equals(AppConfig.load(this).key))editor.setText(Draft.rawText);
  });restoreRaw.setLayoutParams(new LinearLayout.LayoutParams(0,dp(52),1));}
  LinearLayout doneRow=new LinearLayout(this);p.addView(doneRow);
  Button cancel=button(doneRow,"取消修改",v->finish());cancel.setLayoutParams(new LinearLayout.LayoutParams(0,dp(52),1));
  Button done=button(doneRow,"完成修改",v->{
   if(Draft.text==null||draftRevision!=Draft.revision||!sessionKey.equals(AppConfig.load(this).key)){Toast.makeText(this,"登入或暫存已變更，這次修改未保存。",Toast.LENGTH_LONG).show();finish();return;}
   Draft.text=editor.getText().toString();Draft.edited=true;Toast.makeText(this,"已保存暫存文字。回原 App 切回 DreamType，按插入。",Toast.LENGTH_LONG).show();finish();});
  done.setLayoutParams(new LinearLayout.LayoutParams(0,dp(52),1));Ui.button(done,true);
 }
 @Override public Object onRetainNonConfigurationInstance(){
  return editor==null?null:new EditorState(original,editor.getText().toString(),sessionKey,editor.getSelectionStart(),editor.getSelectionEnd(),draftRevision);
 }
}
