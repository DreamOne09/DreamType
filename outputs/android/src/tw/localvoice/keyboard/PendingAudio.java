package tw.localvoice.keyboard;
import android.content.Context;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;

final class PendingAudio {
 private static File file(Context c){return new File(c.getNoBackupFilesDir(),"pending-recording.bin");}
 private static String owner(AppConfig config)throws Exception{
  byte[] digest=MessageDigest.getInstance("SHA-256").digest((config.server+"\n"+config.key).getBytes(StandardCharsets.UTF_8));
  StringBuilder text=new StringBuilder();for(byte b:digest)text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return text.toString();
 }
 static synchronized boolean exists(Context c,AppConfig config){
  try{return config.accountMode&&EncryptedRecording.available(file(c),owner(config),System.currentTimeMillis());}catch(Exception e){return false;}
 }
 static synchronized EncryptedRecording.Entry prepare(Context c,AppConfig config,File audio)throws Exception{
  if(!AppConfig.load(c).key.equals(config.key))throw new Exception("帳號已變更，錄音未送出。");
  if(exists(c,config))throw new Exception("上一段錄音仍保留中，請先重試或刪除。");
  String id=UUID.randomUUID().toString();byte[] data=Files.readAllBytes(audio.toPath());
  EncryptedRecording.save(file(c),AppConfig.secret(),owner(config),id,data,System.currentTimeMillis(),config);
  return new EncryptedRecording.Entry(id,data,config.mode,config.targetLanguage,config.sourceLanguage);
 }
 static synchronized EncryptedRecording.Entry read(Context c,AppConfig config)throws Exception{
  return EncryptedRecording.read(file(c),AppConfig.secret(),owner(config),System.currentTimeMillis());
 }
 static synchronized void clear(Context c){file(c).delete();new File(file(c).getPath()+".tmp").delete();}
 static synchronized void clearIfRequest(Context c,AppConfig config,String id){
  try{if(AppConfig.load(c).key.equals(config.key)&&EncryptedRecording.matches(file(c),owner(config),id))clear(c);}catch(Exception ignored){}
 }
}
