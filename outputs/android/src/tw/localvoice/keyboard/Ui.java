package tw.localvoice.keyboard;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.widget.Button;
final class Ui {
 static final int INK=Color.rgb(24,24,27), MUTED=Color.rgb(82,82,91), PAPER=Color.rgb(250,250,250), LINE=Color.rgb(228,228,231);
 static void button(Button b,boolean primary){
  float d=b.getResources().getDisplayMetrics().density;
  GradientDrawable shape=new GradientDrawable();shape.setColor(primary?INK:Color.WHITE);shape.setCornerRadius(16*d);if(!primary)shape.setStroke((int)d,LINE);
  b.setBackgroundTintList(null);b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x22777777),shape,null));
  b.setTextColor(new ColorStateList(new int[][]{new int[]{-android.R.attr.state_enabled},new int[]{}},new int[]{Color.rgb(140,140,145),primary?Color.WHITE:INK}));
  b.setStateListAnimator(null);b.setElevation(0);b.setAllCaps(false);b.setMinimumHeight((int)(48*d));
 }
}
