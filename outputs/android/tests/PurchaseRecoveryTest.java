package tw.localvoice.keyboard;
import java.util.*;
public final class PurchaseRecoveryTest {
 public static void main(String[] args) throws Exception {
  List<String> calls=new ArrayList<>();
  PurchaseRecovery.Result r=PurchaseRecovery.verifyAll(Arrays.asList("old","new","new"),token->{calls.add(token);if(token.equals("old"))throw new Exception("expired");});
  check(calls.equals(Arrays.asList("old","new")));check(r.confirmed==1&&r.failed==1);
  PurchaseRecovery.Result empty=PurchaseRecovery.verifyAll(Collections.emptyList(),token->{throw new AssertionError();});
  check(empty.confirmed==0&&empty.failed==0);
  calls.clear();boolean stopped=false;
  try{PurchaseRecovery.verifyAll(Arrays.asList("one","two"),token->{calls.add(token);throw new InterruptedException();});}catch(InterruptedException expected){stopped=true;}
  check(stopped&&calls.size()==1);
  System.out.println("Purchase recovery batch checks passed");
 }
 private static void check(boolean b){if(!b)throw new AssertionError();}
}
