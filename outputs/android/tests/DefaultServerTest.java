package tw.localvoice.keyboard;
public class DefaultServerTest {
 public static void main(String[] args)throws Exception {
  if(!AppConfig.setupServer("").equals(AppConfig.DEFAULT_SERVER))throw new AssertionError("Fresh setup has no server");
  if(!AppConfig.setupServer(null).equals(AppConfig.DEFAULT_SERVER))throw new AssertionError("Missing setup has no server");
  String custom="https://own.example";
  if(!AppConfig.setupServer(custom).equals(custom))throw new AssertionError("Saved server overwritten");
  if(!AppConfig.normalize(AppConfig.DEFAULT_SERVER).equals(AppConfig.DEFAULT_SERVER))throw new AssertionError("Invalid default server");
  if(new AppConfig(AppConfig.DEFAULT_SERVER,"",false).ready())throw new AssertionError("Default endpoint bypassed authentication");
  System.out.println("PASS: default setup address, saved address preservation and credentials still required");
 }
}
