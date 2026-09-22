package tw.localvoice.keyboard;

import android.app.Activity;
import android.os.Bundle;
import android.widget.*;

/** Offline factual disclosure for the current invitation beta, not a store policy. */
public final class PrivacyActivity extends Activity {
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void text(LinearLayout page,String value,int size){
        TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(Ui.INK);
        view.setTextIsSelectable(true);view.setPadding(0,dp(12),0,dp(8));page.addView(view);
    }
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Ui.PAPER);
        LinearLayout page=new LinearLayout(this);page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(24),dp(24),dp(24),dp(24));scroll.addView(page);setContentView(scroll);
        scroll.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(i.getSystemWindowInsetLeft(),i.getSystemWindowInsetTop(),i.getSystemWindowInsetRight(),i.getSystemWindowInsetBottom());return i;});
        text(page,"資料與隱私",28);
        text(page,"目前版本為免費邀請試用，沒有訂閱付款。以下說明可離線閱讀。",16);
        text(page,"錄音會送去哪裡？",20);
        text(page,"只有按下錄音才使用麥克風。錄音會經網路傳到你設定的服務主機，進行辨識、整理或翻譯。目前由管理者家中的電腦執行 AI；手機本身不是離線辨識。若連線使用 Cloudflare，錄音會經過其 HTTPS 代理，不是手機到主機的端對端加密。",16);
        text(page,"哪些資料會留下？",20);
        text(page,"帳號模式會在主機保存帳號、密碼雜湊、個人提示詞、詞庫與用量。主機加密暫存待處理錄音，成功或失敗後清除；超過一小時的待處理錄音於重啟時清理。結果加密保留約 15 分鐘，供取回；停機時會等下次啟動清理。",16);
        text(page,"手機帳號模式會加密保留一份未完成錄音，供網路中斷時重試。最長一小時；到期後不能重試，於下次使用清理。成功、登出或手動清除時也會移除。手機另保存加密登入憑證與設定。私人金鑰連線模式不使用帳號佇列的持久結果取回。",16);
        text(page,"如何刪除？",20);
        text(page,"在「我的帳號」選擇「刪除我的帳號」並輸入密碼，可刪除線上帳號與關聯資料。沒有 App 時，也可開啟服務網址後加上 /account。只移除手機登入資料不等於刪除帳號。已插入其他 App 的文字，須在該 App 自行處理。",16);
        text(page,"歷史加密備份不會立即改寫。主機會持續保留不含姓名的帳號 ID 與刪除時間，還原時用於避免已刪帳號重新出現。備份保留期限與異機同步仍在完善；升級前的刪除歷史可能不完整。",16);
        text(page,"連線或資料問題",20);
        text(page,"請聯絡提供試用帳號的管理者。主機需保持開啟；臨時網址變更時，需更新連線設定。這是試用版資料說明，正式上架前仍需提供營運者聯絡資訊與完整隱私政策。",16);
        Button back=new Button(this);back.setText("返回");Ui.button(back,false);back.setOnClickListener(v->finish());page.addView(back,new LinearLayout.LayoutParams(-1,dp(56)));
    }
}
