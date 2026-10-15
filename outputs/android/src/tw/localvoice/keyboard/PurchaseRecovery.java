package tw.localvoice.keyboard;

import java.util.List;
import java.util.HashSet;
import java.util.Set;

/** One failed old token must not prevent verification of other purchases. */
final class PurchaseRecovery {
 interface Verifier { void verify(String token) throws Exception; }
 static final class Result {
  final int confirmed,failed;
  Result(int confirmed,int failed){this.confirmed=confirmed;this.failed=failed;}
 }
 static Result verifyAll(List<String> tokens,Verifier verifier) throws InterruptedException {
  Set<String> seen=new HashSet<>();int confirmed=0,failed=0;
  for(String token:tokens){
   if(Thread.currentThread().isInterrupted())throw new InterruptedException();
   if(token==null||token.isEmpty()||!seen.add(token))continue;
   try{verifier.verify(token);confirmed++;}
   catch(InterruptedException interrupted){throw interrupted;}
   catch(Exception unavailable){failed++;}
  }
  return new Result(confirmed,failed);
 }
}
