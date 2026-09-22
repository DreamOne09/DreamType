package tw.dreamtype.fixture;
import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;
import android.widget.*;
import android.text.InputType;

/** Disposable external editor for testing the real IME; never distributed. */
public final class InputFixture extends Activity {
 @Override public void onCreate(Bundle saved){super.onCreate(saved);
  LinearLayout page=new LinearLayout(this);page.setOrientation(1);page.setPadding(24,64,24,16);
  page.setFocusableInTouchMode(true);
  TextView title=new TextView(this);title.setText("DreamType 輸入法測試");title.setTextSize(20);page.addView(title);
  EditText normal=new EditText(this);normal.setId(101);normal.setHint("一般文字");normal.setContentDescription("一般文字");normal.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);page.addView(normal,new LinearLayout.LayoutParams(-1,80));
  EditText password=new EditText(this);password.setId(102);password.setHint("密碼欄位");password.setContentDescription("密碼欄位");password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);page.addView(password,new LinearLayout.LayoutParams(-1,80));
  setContentView(page);page.requestFocus();getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
 }
}
