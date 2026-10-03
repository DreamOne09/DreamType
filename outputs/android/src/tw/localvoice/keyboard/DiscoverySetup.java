package tw.localvoice.keyboard;
import android.app.Activity;
import android.widget.EditText;
import android.widget.TextView;
import java.util.concurrent.ExecutorService;

/** Changes only the visible address field, never credentials or saved sessions. */
final class DiscoverySetup {
 static void refresh(Activity activity,EditText address,TextView status,ExecutorService worker){
  String before=address.getText().toString();AppConfig session=AppConfig.load(activity);
  status.setText("正在取得最新服務網址…");
  worker.execute(()->{
   try{
    long minimum=activity.getSharedPreferences("discovery",0).getLong("serial",0);
    ServiceDiscovery.Endpoint endpoint=ServiceDiscovery.fetch(minimum);
    activity.runOnUiThread(()->apply(activity,address,status,before,session,endpoint));
   }catch(Exception error){activity.runOnUiThread(()->{if(!activity.isDestroyed()&&!activity.isFinishing()&&address.isAttachedToWindow()&&before.equals(address.getText().toString())&&AppConfig.load(activity).sameSession(session))status.setText("暫時無法取得可信的最新網址。保留原設定，請稍後重試或向管理者確認。");});}
  });
 }
 static void apply(Activity activity,EditText address,TextView status,String before,AppConfig session,ServiceDiscovery.Endpoint endpoint){
     if(activity.isDestroyed()||activity.isFinishing()||!address.isAttachedToWindow())return;
     if(!AppConfig.load(activity).sameSession(session)||!before.equals(address.getText().toString()))return;
     synchronized(ServiceDiscovery.class){
      android.content.SharedPreferences saved=activity.getSharedPreferences("discovery",0);
      if(endpoint.serial<saved.getLong("serial",0)||endpoint.expires<=System.currentTimeMillis()/1000){status.setText("網址資料已過期，請稍後再試。");return;}
      if(!saved.edit().putLong("serial",endpoint.serial).commit()){status.setText("無法記錄網址驗證結果，請稍後再試。");return;}
     }
     address.setText(endpoint.url);
     status.setText("已帶入最新網址，請確認後登入或測試連線。");

 }
}
