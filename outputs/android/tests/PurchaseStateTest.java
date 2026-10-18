package tw.localvoice.keyboard;

public final class PurchaseStateTest {
 private static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  PurchaseState state=new PurchaseState();check(!state.known());
  long query=state.beginQuery();check(state.applyQuery(query,1));check(state.owned());
  // Expiry/cancellation observed by a new successful query clears stale ownership.
  query=state.beginQuery();check(!state.known());check(state.applyQuery(query,0));
  check(state.known()&&!state.owned());
  // A checkout callback races an older empty-query response: never reopen checkout.
  query=state.beginQuery();state.observedPurchase();check(!state.applyQuery(query,0));
  check(!state.known()&&state.owned());
  query=state.beginQuery();check(state.applyQuery(query,1));check(state.known()&&state.owned());
  // A failed query has no apply step, so prior ownership cannot become buyable.
  state.beginQuery();check(!state.known()&&state.owned());
  System.out.println("PurchaseStateTest passed");
 }
}
