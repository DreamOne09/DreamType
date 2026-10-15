package tw.localvoice.keyboard;
public final class AccountPlanTest {
 public static void main(String[] args){
  check(AccountPlan.describe("closed-beta","").contains("尚未收費"));
  check(AccountPlan.describe("pro","active").equals("訂閱使用中"));
  check(!AccountPlan.describe("pro","").contains("訂閱使用中"));
  check(AccountPlan.describe("subscription","verification_required").contains("正在確認"));
  check(AccountPlan.describe("subscription","entitlement_conflict").contains("聯絡管理者"));
  check(AccountPlan.describe("subscription","subscription_required").contains("沒有可用訂閱"));
  check(AccountPlan.minutes(59).equals("不到 1"));
  check(AccountPlan.minutes(60).equals("1"));
  check(AccountPlan.minutes(0).equals("0"));
  System.out.println("Account plan state checks passed");
 }
 private static void check(boolean value){if(!value)throw new AssertionError();}
}
