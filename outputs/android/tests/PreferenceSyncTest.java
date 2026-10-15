package tw.localvoice.keyboard;
import android.content.*;import java.lang.reflect.*;import java.util.*;import java.nio.file.*;import org.json.*;
public class PreferenceSyncTest {
 static class Store {
  Map<String,Object> values=new HashMap<>();boolean fail=false;int commits=0;
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.class},(p,m,a)->{
   if(m.getName().equals("edit"))return editor();
   if(m.getName().equals("contains"))return values.containsKey(a[0]);
   if(m.getName().startsWith("get"))return values.containsKey(a[0])?values.get(a[0]):a[1];
   return null;
  });
  SharedPreferences.Editor editor(){Map<String,Object> pending=new HashMap<>();return (SharedPreferences.Editor)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.Editor.class},(p,m,a)->{
   if(m.getName().startsWith("put")){pending.put((String)a[0],a[1]);return p;}
   if(m.getName().equals("commit")){commits++;if(fail)return false;values.putAll(pending);return true;}
   return p;
  });}
 }
 static class FakeContext extends Context {
  Store style=new Store(),connection=new Store();
  public SharedPreferences getSharedPreferences(String n,int mode){return n.equals("style")?style.prefs:connection.prefs;}
 }
 interface Operation {void run()throws Exception;}
 static void fails(Operation action)throws Exception{try{action.run();throw new AssertionError("Expected save failure");}catch(java.io.IOException expected){}}
 static FakeContext context(){FakeContext c=new FakeContext();c.connection.values.put("server","https://one.invalid");c.connection.values.put("account",true);return c;}
 static PreferenceSync.Store store(FakeContext c){return new PreferenceSync.Store(){public AppConfig current(){return AppConfig.load(c);}public void persist(AppConfig expected,JSONObject p,boolean auto)throws Exception{AppConfig.savePreferences(c,expected,p,auto);}};}
 public static void main(String[] args)throws Exception{
  JSONObject prefs=new JSONObject().put("vocabulary","synthetic"),report=new JSONObject();
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);int[] calls={0};
   c.connection.values.put("server","https://two.invalid");
   fails(()->PreferenceSync.save(expected,prefs,false,store(c),(e,p)->calls[0]++));
   if(calls[0]!=0||c.style.commits!=0)throw new AssertionError("Changed host was written");
   report.put("changed_host_rejected_before_remote",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);int[] calls={0};c.connection.values.put("account",false);
   fails(()->PreferenceSync.save(expected,prefs,false,store(c),(e,p)->calls[0]++));
   if(calls[0]!=0||c.style.commits!=0)throw new AssertionError("Changed mode was written");
   report.put("changed_auth_mode_rejected",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);
   fails(()->PreferenceSync.save(expected,prefs,false,store(c),(e,p)->{throw new java.net.SocketTimeoutException("synthetic timeout");}));
   if(c.style.commits!=0||c.connection.commits!=0)throw new AssertionError("Failure saved locally");
   report.put("remote_failure_no_local_success",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);
   fails(()->PreferenceSync.save(expected,prefs,false,store(c),(e,p)->c.connection.values.put("server","https://two.invalid")));
   if(c.style.commits!=0)throw new AssertionError("Replaced session was overwritten");
   report.put("session_changed_during_request_rejected",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);c.style.fail=true;
   fails(()->PreferenceSync.save(expected,prefs,false,store(c),(e,p)->{}));
   report.put("style_commit_failure_reported",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);c.connection.fail=true;
   fails(()->PreferenceSync.save(expected,prefs,true,store(c),(e,p)->{}));
   report.put("auto_commit_failure_reported",true);}
  {FakeContext c=context();AppConfig expected=AppConfig.load(c);int[] calls={0};
   PreferenceSync.save(expected,prefs,true,store(c),(e,p)->calls[0]++);
   if(calls[0]!=1||!"synthetic".equals(c.style.values.get("vocabulary"))||!Boolean.TRUE.equals(c.connection.values.get("auto")))throw new AssertionError("Successful save missing");
   report.put("success_persisted",true);}
  {FakeContext c=context();c.connection.values.put("account",false);AppConfig expected=AppConfig.load(c);
   PreferenceSync.save(expected,prefs,false,store(c),(e,p)->{throw new AssertionError("Private mode called account API");});
   report.put("private_mode_local_only",true);}
  Files.writeString(Paths.get(args[0]),report.toString(2),StandardOpenOption.CREATE_NEW);System.out.println(report.toString());
 }
}
