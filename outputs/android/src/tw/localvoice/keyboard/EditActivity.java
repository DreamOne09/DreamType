package tw.localvoice.keyboard;
import android.app.Activity;
import android.os.Bundle;
import android.content.*;
import android.view.*;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

public final class EditActivity extends Activity {
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private void button(LinearLayout p,String label,View.OnClickListener action){Button b=new Button(this);b.setText(label);Ui.button(b,false);b.setOnClickListener(action);p.addView(b,new LinearLayout.LayoutParams(-1,dp(52)));}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  if(Draft.text==null){Toast.makeText(this,"暫存文字已清除，請重新錄音。",Toast.LENGTH_LONG).show();finish();return;}
  final String original=Draft.text;
  LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(20),dp(16),dp(20),dp(16));p.setBackgroundColor(Ui.PAPER);setContentView(p);
  p.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(dp(20)+i.getSystemWindowInsetLeft(),dp(16)+i.getSystemWindowInsetTop(),dp(20)+i.getSystemWindowInsetRight(),dp(16)+i.getSystemWindowInsetBottom());return i;});
  TextView title=new TextView(this);title.setText("修改文字");title.setTextColor(Ui.INK);title.setTextSize(24);p.addView(title);
  TextView hint=new TextView(this);hint.setText("可切換 Gboard 修改。完成後回到原 App，切回 DreamType，再按「插入」。");hint.setTextColor(Ui.MUTED);hint.setTextSize(15);p.addView(hint);
  EditText editor=new EditText(this);editor.setText(original);editor.setTextColor(Ui.INK);editor.setTextSize(18);editor.setGravity(Gravity.TOP);editor.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);editor.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);p.addView(editor,new LinearLayout.LayoutParams(-1,0,1));
  button(p,"切換打字鍵盤",v->((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker());
  button(p,"復原這次修改",v->editor.setText(original));
  button(p,"完成修改",v->{Draft.text=editor.getText().toString();Draft.edited=true;Toast.makeText(this,"已保存暫存文字。回原 App 切回 DreamType，按插入。",Toast.LENGTH_LONG).show();finish();});
 }
}
