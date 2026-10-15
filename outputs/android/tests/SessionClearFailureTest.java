package tw.localvoice.keyboard;
import android.content.*;
import java.lang.reflect.Proxy;
import java.nio.file.*;
import java.util.*;
import org.json.JSONObject;

/** Real clearSession with memory/disk preference simulation, not Android disk/Keystore. */
public final class SessionClearFailureTest {
 static final class Store {
  final Map<String,Object> memory=new HashMap<>(),disk=new HashMap<>();boolean fail;
  void seed(String key,Object value){memory.put(key,value);disk.put(key,value);}
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.class},(p,m,a)->{
   if(m.getName().equals("edit"))return editor();
   if(m.getName().equals("contains"))return memory.containsKey(a[0]);
   if(m.getName().startsWith("get"))return memory.containsKey(a[0])?memory.get(a[0]):a[1];
   return null;
  });
  SharedPreferences.Editor editor(){Map<String,Object> changes=new HashMap<>();boolean[] clear={false};
   return (SharedPreferences.Editor)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.Editor.class},(p,m,a)->{
    if(m.getName().equals("clear")){clear[0]=true;return p;}
    if(m.getName().startsWith("put")){changes.put((String)a[0],a[1]);return p;}
    if(m.getName().equals("commit")){
     // Android may update memory even when disk commit returns false.
     if(clear[0])memory.clear();memory.putAll(changes);
     if(fail)return false;disk.clear();disk.putAll(memory);return true;
    }return p;
   });
  }
 }
 static final class TestContext extends Context {
  final Store connection=new Store(),style=new Store();final java.io.File dir;
  TestContext(Path p){dir=p.toFile();connection.seed("server","https://synthetic.invalid");connection.seed("account",true);style.seed("vocabulary","synthetic-only");}
  public SharedPreferences getSharedPreferences(String name,int mode){return name.equals("connection")?connection.prefs:style.prefs;}
  public java.io.File getNoBackupFilesDir(){return dir;}
 }
 public static void main(String[] args)throws Exception {
  Path report=Paths.get(args[0]);if(Files.exists(report))throw new IllegalArgumentException("Evidence exists");
  Path dir=Files.createTempDirectory("session-clear-contract-");JSONObject cases=new JSONObject();boolean passed=true;
  try{
   for(int i=0;i<3;i++){
    TestContext c=new TestContext(dir);c.connection.fail=i==1;c.style.fail=i==2;
    Files.write(dir.resolve("pending-recording.bin"),new byte[]{1,2,3});
    Files.write(dir.resolve("pending-recording.bin.tmp"),new byte[]{4});Draft.begin("synthetic draft","synthetic raw");
    Exception failure=null;try{AppConfig.clearSession(c);}catch(Exception e){failure=e;}
    boolean ok=(i==0?failure==null:failure instanceof java.io.IOException);
    boolean cleaned=!Files.exists(dir.resolve("pending-recording.bin"))&&!Files.exists(dir.resolve("pending-recording.bin.tmp"))&&Draft.text==null;
    ok &= cleaned;
    if(i==0)ok &= c.style.disk.isEmpty()&&c.connection.disk.size()==1&&"https://synthetic.invalid".equals(c.connection.disk.get("server"));
    cases.put(i==0?"successful_clear":i==1?"connection_disk_failure":"style_disk_failure",new JSONObject()
      .put("passed",ok).put("failure_reported",failure!=null).put("transient_data_cleared",cleaned)
      .put("connection_disk_still_has_account",c.connection.disk.containsKey("account"))
      .put("style_disk_still_has_vocabulary",c.style.disk.containsKey("vocabulary")));
    passed &= ok;
   }
   Path blocked=dir.resolve("pending-recording.bin");Files.createDirectory(blocked);
   Files.write(blocked.resolve("obstruction"),new byte[]{1});
   Files.write(dir.resolve("pending-recording.bin.tmp"),new byte[]{2});
   boolean rejected=false;try{AppConfig.clearSession(new TestContext(dir));}catch(java.io.IOException expected){rejected=true;}
   boolean deletionFailure=rejected&&Files.exists(blocked.resolve("obstruction"))&&!Files.exists(dir.resolve("pending-recording.bin.tmp"));
   cases.put("recording_delete_failure_reported_and_temp_cleanup_attempted",deletionFailure);passed &= deletionFailure;
   Files.delete(blocked.resolve("obstruction"));Files.delete(blocked);
  }finally{Files.deleteIfExists(dir.resolve("pending-recording.bin/obstruction"));Files.deleteIfExists(dir.resolve("pending-recording.bin"));Files.deleteIfExists(dir.resolve("pending-recording.bin.tmp"));Files.delete(dir);}
  JSONObject result=new JSONObject().put("scope","Actual clearSession; synthetic Context/preferences, disk-vs-memory simulation. No native disk/Keystore or real accounts.").put("cases",cases).put("passed",passed);
  Files.write(report,result.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Session clear: passed="+passed+"; evidence saved");if(!passed)throw new AssertionError("See session clear evidence");
 }
}
