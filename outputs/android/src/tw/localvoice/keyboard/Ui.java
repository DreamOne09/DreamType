package tw.localvoice.keyboard;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.widget.Button;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
final class Ui {
 static final int INK=Color.rgb(24,24,27), MUTED=Color.rgb(82,82,91), PAPER=Color.rgb(250,250,250), LINE=Color.rgb(228,228,231);
 static void button(Button b,boolean primary){
  float d=b.getResources().getDisplayMetrics().density;
  GradientDrawable shape=new GradientDrawable();shape.setColor(primary?INK:Color.WHITE);shape.setCornerRadius(16*d);if(!primary)shape.setStroke((int)d,LINE);
  b.setBackgroundTintList(null);b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x22777777),shape,null));
  b.setTextColor(new ColorStateList(new int[][]{new int[]{-android.R.attr.state_enabled},new int[]{}},new int[]{Color.rgb(140,140,145),primary?Color.WHITE:INK}));
  b.setStateListAnimator(null);b.setElevation(0);b.setAllCaps(false);b.setMinimumHeight((int)(48*d));
 }
 static void quiet(Button b){
  button(b,false);GradientDrawable shape=new GradientDrawable();shape.setColor(Color.TRANSPARENT);shape.setCornerRadius(12*b.getResources().getDisplayMetrics().density);
  b.setBackground(new RippleDrawable(ColorStateList.valueOf(0x18777777),shape,null));
 }
 /** Small local vector glyphs: consistent stroke, no font-dependent emoji. */
 static void symbol(Button button,String name,int color,int size){
  final int pixels=Math.round(size*button.getResources().getDisplayMetrics().density);
  Drawable glyph=new Drawable(){
   private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
   public int getIntrinsicWidth(){return pixels;}public int getIntrinsicHeight(){return pixels;}
   public void setAlpha(int alpha){p.setAlpha(alpha);invalidateSelf();}
   public void setColorFilter(android.graphics.ColorFilter f){p.setColorFilter(f);invalidateSelf();}
   public int getOpacity(){return android.graphics.PixelFormat.TRANSLUCENT;}
   public void draw(Canvas c){
    c.save();c.translate(getBounds().left,getBounds().top);c.scale(getBounds().width()/24f,getBounds().height()/24f);
    p.setColor(color);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(1.7f);p.setStrokeCap(Paint.Cap.ROUND);p.setStrokeJoin(Paint.Join.ROUND);
    Path path=new Path();
    if(name.equals("mic")){c.drawRoundRect(new RectF(8,2,16,15),4,4,p);c.drawArc(new RectF(5,5,19,19),0,180,false,p);c.drawLine(5,10,5,12,p);c.drawLine(19,10,19,12,p);c.drawLine(12,19,12,22,p);c.drawLine(8,22,16,22,p);}
    else if(name.equals("stop")){p.setStyle(Paint.Style.FILL);c.drawRoundRect(new RectF(5,5,19,19),3,3,p);}
    else if(name.equals("insert")){path.moveTo(5,12);path.lineTo(10,17);path.lineTo(19,7);c.drawPath(path,p);}
    else if(name.equals("retry")){c.drawArc(new RectF(4,4,20,20),-60,290,false,p);path.moveTo(4,4);path.lineTo(4,10);path.lineTo(10,10);c.drawPath(path,p);}
    else if(name.equals("backspace")){path.moveTo(8,5);path.lineTo(21,5);path.lineTo(21,19);path.lineTo(8,19);path.lineTo(2,12);path.close();c.drawPath(path,p);c.drawLine(12,9,17,15,p);c.drawLine(17,9,12,15,p);}
    else if(name.equals("keyboard")){c.drawRoundRect(new RectF(2,5,22,19),3,3,p);for(int x=6;x<=18;x+=4){c.drawPoint(x,9,p);c.drawPoint(x,12,p);}c.drawLine(8,16,16,16,p);}
    else {c.drawCircle(5,12,1,p);c.drawCircle(12,12,1,p);c.drawCircle(19,12,1,p);}
    c.restore();
   }
  };
  button.setCompoundDrawablesWithIntrinsicBounds(null,glyph,null,null);button.setCompoundDrawablePadding(Math.round(6*button.getResources().getDisplayMetrics().density));
 }
}
