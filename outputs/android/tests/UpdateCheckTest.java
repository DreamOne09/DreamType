package tw.localvoice.keyboard;
public class UpdateCheckTest {
 public static void main(String[] args)throws Exception {
  if(!UpdateCheck.newer("v0.3.0","0.2.0"))throw new AssertionError("upgrade");
  if(!UpdateCheck.newer("v0.10.0","0.9.0"))throw new AssertionError("numeric comparison");
  if(UpdateCheck.newer("v0.3.0","0.3.0")||UpdateCheck.newer("v0.2.0","0.3.0"))throw new AssertionError("no downgrade");
  if(UpdateCheck.newer("v0.4.0-beta","0.3.0")||UpdateCheck.newer("invalid","0.3.0"))throw new AssertionError("stable only");
  System.out.println("Version upgrade/downgrade checks passed. GitHub latest: "+UpdateCheck.latest());
 }
}
