package tw.localvoice.keyboard;
import android.content.*;import java.lang.reflect.*;import java.util.*;import java.nio.file.*;import org.json.*;
public class PendingAudioSessionTest {
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
  java.io.File directory; public java.io.File getNoBackupFilesDir(){return directory;}
  public SharedPreferences getSharedPreferences(String n,int mode){return n.equals("style")?style.prefs:connection.prefs;}
 }
 static String owner(AppConfig c)throws Exception{byte[] digest=java.security.MessageDigest.getInstance("SHA-256").digest((c.server+"\n"+c.key).getBytes(java.nio.charset.StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte b:digest)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}
 public static void main(String[] args)throws Exception{
  Path dir=Files.createTempDirectory("pending-session-contract-");
  try{
   FakeContext c=new FakeContext();c.directory=dir.toFile();c.connection.values.put("server","https://old.invalid");c.connection.values.put("account",true);
   AppConfig old=AppConfig.load(c);c.connection.values.put("server","https://new.invalid");AppConfig current=AppConfig.load(c);
   java.io.File file=dir.resolve("pending-recording.bin").toFile();
   EncryptedRecording.save(file,new javax.crypto.spec.SecretKeySpec(new byte[16],"AES"),owner(current),"synthetic-request-0001",new byte[]{1,2,3},System.currentTimeMillis(),current);
   boolean before=PendingAudio.exists(c,current);boolean stale=PendingAudio.exists(c,old);boolean survived=file.exists();
   JSONObject result=new JSONObject().put("current_recording_available",before).put("stale_check_returns_false",!stale).put("current_recording_survives_stale_check",survived);

   if(!before||stale||!survived)throw new AssertionError("Stale availability check damaged recording");
   byte[] original=Files.readAllBytes(file.toPath());
   try{PendingAudio.prepare(c,old,new java.io.File("unused-synthetic-audio"));throw new AssertionError("Stale prepare accepted");}catch(java.io.IOException expected){}
   try{PendingAudio.read(c,old);throw new AssertionError("Stale retry accepted");}catch(java.io.IOException expected){}
   PendingAudio.clearIfRequest(c,old,"synthetic-request-0001");
   if(!java.util.Arrays.equals(original,Files.readAllBytes(file.toPath())))throw new AssertionError("Stale operation modified file");
   result.put("stale_prepare_read_clear_preserve_bytes",true);
   PendingAudio.clearIfRequest(c,current,"different-request-0002");
   if(!file.exists())throw new AssertionError("Wrong receipt cleared file");
   result.put("different_request_not_cleared",true);
   c.connection.values.put("account",false);
   if(PendingAudio.exists(c,current)||!java.util.Arrays.equals(original,Files.readAllBytes(file.toPath())))throw new AssertionError("Changed authorization mode accessed recording");
   result.put("changed_mode_rejected_preserving_recording",true);
   c.connection.values.put("account",true);
   PendingAudio.clearIfRequest(c,current,"synthetic-request-0001");
   if(file.exists())throw new AssertionError("Current matching receipt did not clear");
   result.put("current_matching_receipt_clears",true);
   Files.writeString(Paths.get(args[0]),result.toString(2),StandardOpenOption.CREATE_NEW);System.out.println(result.toString());
  }finally{Files.deleteIfExists(dir.resolve("pending-recording.bin"));Files.deleteIfExists(dir.resolve("pending-recording.bin.tmp"));Files.delete(dir);}
 }
}
