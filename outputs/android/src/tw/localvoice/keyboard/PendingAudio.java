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
  // available() may delete an expired/wrong-owner file. A stale caller must
  // never inspect it after another session has replaced the recording.
  try{return config.accountMode&&AppConfig.load(c).sameSession(config)&&EncryptedRecording.available(file(c),owner(config),System.currentTimeMillis());}catch(Exception e){return false;}
 }
 private static void requireCurrent(Context c,AppConfig config)throws java.io.IOException {
  if(!config.accountMode||!AppConfig.load(c).sameSession(config))
   throw new java.io.IOException("登入或連線已變更，保留錄音未讀取或修改，請重新開啟鍵盤。");
 }
 static synchronized EncryptedRecording.Entry prepare(Context c,AppConfig config,File audio)throws Exception{
  requireCurrent(c,config);
  if(exists(c,config))throw new Exception("上一段錄音仍保留中，請先重試或刪除。");
  String id=UUID.randomUUID().toString();byte[] data=Files.readAllBytes(audio.toPath());
  EncryptedRecording.save(file(c),AppConfig.secret(),owner(config),id,data,System.currentTimeMillis(),config);
  return new EncryptedRecording.Entry(id,data,config.mode,config.targetLanguage,config.sourceLanguage);
 }
 static synchronized EncryptedRecording.Entry read(Context c,AppConfig config)throws Exception{
  requireCurrent(c,config);
  return EncryptedRecording.read(file(c),AppConfig.secret(),owner(config),System.currentTimeMillis());
 }
 static synchronized void clear(Context c)throws java.io.IOException {
  java.io.IOException failure=null;
  for(File target:new File[]{file(c),new File(file(c).getPath()+".tmp")}){
   try{Files.deleteIfExists(target.toPath());}
   catch(java.io.IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
  }
  if(failure!=null)throw new java.io.IOException("手機未能完整刪除保留錄音，請稍後再試；若持續失敗，請到系統設定清除 DreamType 儲存空間。",failure);
 }
 static synchronized void clearIfRequest(Context c,AppConfig config,String id){
  try{if(config.accountMode&&AppConfig.load(c).sameSession(config)&&EncryptedRecording.matches(file(c),owner(config),id))clear(c);}catch(Exception ignored){}
 }
}
