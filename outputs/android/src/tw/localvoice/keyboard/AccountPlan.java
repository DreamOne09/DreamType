package tw.localvoice.keyboard;

/** Server entitlement status labels. Never infer payment from local settings. */
final class AccountPlan {
 private AccountPlan(){}
 static String describe(String plan,String status){
  if("closed-beta".equals(plan)&&status.isEmpty())return "封閉試用 · 尚未收費";
  if("active".equals(status))return "訂閱使用中";
  if("subscription_required".equals(status))return "目前沒有可用訂閱";
  if("verification_required".equals(status))return "正在確認訂閱，請稍後重新整理";
  if("entitlement_conflict".equals(status))return "訂閱資料需要確認，請聯絡管理者";
  return "尚無法確認方案，請重新整理";
 }
 static String minutes(long seconds){
  if(seconds<=0)return "0";
  if(seconds<60)return "不到 1";
  return Long.toString(seconds/60);
 }
}
