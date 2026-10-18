package tw.localvoice.keyboard;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.view.WindowManager;
import android.widget.*;
import com.android.billingclient.api.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Play-only UI. The server owns all entitlements and acknowledgements. */
public final class PlayBillingActivity extends Activity {
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private final Set<String> allowed=new HashSet<>();
 private final Map<String,Long> allowances=new HashMap<>();
 private AppConfig session;
 private BillingClient billing;
 private TextView status;
 private LinearLayout offers;
 private String accountId;
 private volatile boolean destroyed;
 private final PurchaseState ownership=new PurchaseState();
 private boolean checking,checkout,querying,recheck;
 private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 private boolean current(){return !destroyed&&!isFinishing()&&session.sameSession(AppConfig.load(this));}
 private void message(String text){runOnUiThread(()->{if(current())status.setText(text);});}
 private Button button(LinearLayout parent,String label,Runnable action){
  Button b=new Button(this);b.setText(label);b.setAllCaps(false);parent.addView(b);b.setOnClickListener(v->{if(current())action.run();else finish();});return b;
 }
 @Override public void onCreate(Bundle state){
  super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
  session=AppConfig.load(this);
  if(!session.ready()||!session.accountMode){finish();return;}
  ScrollView scroll=new ScrollView(this);LinearLayout page=new LinearLayout(this);page.setOrientation(LinearLayout.VERTICAL);page.setPadding(dp(24),dp(24),dp(24),dp(24));scroll.addView(page);setContentView(scroll);
  page.setBackgroundColor(Ui.PAPER);TextView title=new TextView(this);title.setText("訂閱 DreamType");title.setTextSize(28);page.addView(title);
  status=new TextView(this);status.setTextSize(16);status.setText("正在確認可用方案…");status.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);page.addView(status);
  offers=new LinearLayout(this);offers.setOrientation(LinearLayout.VERTICAL);page.addView(offers);
  button(page,"恢復購買",this::restore);
  button(page,"管理 Google Play 訂閱",()->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse("https://play.google.com/store/account/subscriptions")));}catch(Exception e){message("無法開啟 Google Play，請從 Play 商店管理訂閱。");}});
  button(page,"資料與隱私",()->startActivity(new Intent(this,PrivacyActivity.class)));
  button(page,"返回",this::finish);
  worker.execute(()->{
   try{
    JSONObject info=VoiceApi.json(session,"GET","/v2/billing/google/account",null);
    String id=info.getString("obfuscated_account_id");if(!id.matches("[0-9a-f]{64}"))throw new Exception();
    JSONArray products=info.getJSONArray("products");List<QueryProductDetailsParams.Product> queries=new ArrayList<>();Set<String> ids=new HashSet<>();Set<String> pairs=new HashSet<>();Map<String,Long> quotas=new HashMap<>();
    if(products.length()<1||products.length()>20)throw new Exception();
    for(int i=0;i<products.length();i++){JSONObject p=products.getJSONObject(i);String product=p.getString("product_id");String pair=product+"\n"+p.getString("base_plan_id");long seconds=p.getLong("monthly_seconds");if(seconds<1||seconds>6000000||!"utc_calendar_month".equals(p.getString("quota_reset")))throw new Exception();pairs.add(pair);quotas.put(pair,seconds);if(ids.add(product))queries.add(QueryProductDetailsParams.Product.newBuilder().setProductId(product).setProductType(BillingClient.ProductType.SUBS).build());}
    runOnUiThread(()->{if(!current())return;accountId=id;allowed.addAll(pairs);allowances.putAll(quotas);connect(queries);});
   }catch(Exception e){message("目前無法取得訂閱方案。若仍為試用服務，代表尚未開放收費。請稍後重新開啟此頁。");}
  });
 }
 private void connect(List<QueryProductDetailsParams.Product> queries){
  billing=BillingClient.newBuilder(this).setListener((result,purchases)->{
   runOnUiThread(()->checkout=false);
   if(result.getResponseCode()==BillingClient.BillingResponseCode.OK)verify(purchases);
   else if(result.getResponseCode()==BillingClient.BillingResponseCode.USER_CANCELED)message("已取消購買，沒有開通新的方案。");
   else message("Google Play 暫時無法完成購買，請恢復購買確認狀態。");
  }).enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build()).enableAutoServiceReconnection().build();
  billing.startConnection(new BillingClientStateListener(){
   public void onBillingSetupFinished(BillingResult result){runOnUiThread(()->{
    if(!current())return;
    if(result.getResponseCode()!=BillingClient.BillingResponseCode.OK){message("無法連接 Google Play，請確認已登入 Play 商店。");return;}
    restore();
    billing.queryProductDetailsAsync(QueryProductDetailsParams.newBuilder().setProductList(queries).build(),(r,details)->runOnUiThread(()->{
     if(!current())return;offers.removeAllViews();
     if(r.getResponseCode()!=BillingClient.BillingResponseCode.OK){message("無法讀取 Google Play 價格，請稍後重開此頁。");return;}
     for(ProductDetails product:details.getProductDetailsList()){
      if(product.getSubscriptionOfferDetails()==null)continue;
      for(ProductDetails.SubscriptionOfferDetails offer:product.getSubscriptionOfferDetails()){
       if(!allowed.contains(product.getProductId()+"\n"+offer.getBasePlanId())||offer.getOfferId()!=null)continue;
       List<ProductDetails.PricingPhase> phases=offer.getPricingPhases().getPricingPhaseList();
       if(phases.size()!=1||phases.get(0).getRecurrenceMode()!=ProductDetails.RecurrenceMode.INFINITE_RECURRING)continue;
       ProductDetails.PricingPhase price=phases.get(0);String period=period(price.getBillingPeriod());if(period==null)continue;
       TextView quota=new TextView(PlayBillingActivity.this);quota.setText("每 UTC 曆月 "+AccountPlan.minutes(allowances.get(product.getProductId()+"\n"+offer.getBasePlanId()))+" 分鐘語音用量；每月重置、不累積。");offers.addView(quota);
       button(offers,product.getName()+" · "+price.getFormattedPrice()+"／"+period,()->buy(product,offer));
      }
     }
     TextView terms=new TextView(PlayBillingActivity.this);terms.setText(offers.getChildCount()==0?"目前沒有可購買的標準方案。":"訂閱會自動續訂，可隨時在 Google Play 管理取消。價格與結帳條件以 Google Play 確認畫面為準。");offers.addView(terms);
    }));
   });}
   public void onBillingServiceDisconnected(){message("Google Play 連線中斷，請稍後重試。");}
  });
 }
 private static String period(String code){if("P1M".equals(code))return "月";if("P1Y".equals(code))return "年";if("P1W".equals(code))return "週";return null;}
 private void buy(ProductDetails product,ProductDetails.SubscriptionOfferDetails offer){
  if(billing==null||!billing.isReady()||checking||checkout){message("請先等候訂閱確認完成。");return;}
  if(ownership.owned()){message("已找到現有購買。請先恢復購買或管理訂閱，避免重複訂閱。");return;}
  if(!ownership.known()){message("請先恢復購買，確認 Google Play 購買紀錄。");return;}
  BillingFlowParams params=BillingFlowParams.newBuilder().setObfuscatedAccountId(accountId).setProductDetailsParamsList(Collections.singletonList(BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(product).setOfferToken(offer.getOfferToken()).build())).build();
  checkout=true;
  BillingResult result=billing.launchBillingFlow(this,params);
  if(result.getResponseCode()!=BillingClient.BillingResponseCode.OK){checkout=false;message("無法開啟 Google Play 結帳，請稍後重試。");}
 }
 private void restore(){
  if(billing==null||!billing.isReady()){message("請等候 Google Play 連線，或稍後重開此頁。");return;}
  if(checking||querying){recheck=true;return;}
  querying=true;final long queryRevision=ownership.beginQuery();
  billing.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build(),(result,purchases)->runOnUiThread(()->{
   querying=false;
   if(!current())return;
   if(result.getResponseCode()!=BillingClient.BillingResponseCode.OK){message("無法讀取購買紀錄，請稍後重試。");return;}
   if(!ownership.applyQuery(queryRevision,purchases.size())){restore();return;}
   verify(purchases);
  }));
 }
 private void verify(List<Purchase> purchases){
  runOnUiThread(()->{
   if(!current())return;
   if(purchases!=null&&!purchases.isEmpty())ownership.observedPurchase();
   if(checking){recheck=true;return;}
   if(purchases==null||purchases.isEmpty()){message("此 Google Play 帳號目前沒有可恢復的訂閱。");if(recheck){recheck=false;restore();}return;}
   checking=true;message("正在由服務確認購買，請勿重複付款…");
   worker.execute(()->{
    String result="付款仍在等待確認，完成後請恢復購買。";
    try{
     List<String> tokens=new ArrayList<>();
     for(Purchase purchase:purchases){
      if(!current())return;
      if(purchase.getPurchaseState()!=Purchase.PurchaseState.PURCHASED)continue;
      tokens.add(purchase.getPurchaseToken());
     }
     PurchaseRecovery.Result recovered=PurchaseRecovery.verifyAll(tokens,token->{
      if(!current())throw new InterruptedException();
      VoiceApi.json(session,"POST","/v2/billing/google/verify",new JSONObject().put("purchase_token",token));
     });
     if(!tokens.isEmpty()&&current()){
      JSONObject me=VoiceApi.json(session,"GET","/v2/me",null);result=AccountPlan.describe(me.optString("plan"),me.optString("entitlement_status"));
      if(recovered.failed>0)result+="\n部分購買紀錄尚未確認；請稍後恢復購買，勿重複付款。";
     }
    }catch(Exception e){result="購買尚未確認。請使用相同 DreamType 與 Google Play 帳號，再按恢復購買；請勿重複付款。";}
    final String label=result;runOnUiThread(()->{checking=false;if(current()){status.setText(label);if(recheck){recheck=false;restore();}}});
   });
  });
 }
 @Override protected void onResume(){super.onResume();if(billing!=null&&billing.isReady()&&current()){checkout=false;restore();}}
 @Override protected void onDestroy(){destroyed=true;if(billing!=null)billing.endConnection();worker.shutdownNow();super.onDestroy();}
}
