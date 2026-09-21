package tw.localvoice.keyboard;
import java.nio.file.*;
import java.io.File;
import java.util.Arrays;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;

public class EncryptedRecordingTest {
 public static void main(String[] args)throws Exception{
  Path directory=Files.createTempDirectory("dreamtype-recording-test-");File file=directory.resolve("recording.bin").toFile();
  KeyGenerator generator=KeyGenerator.getInstance("AES");generator.init(256);SecretKey key=generator.generateKey();
  String owner=String.join("",java.util.Collections.nCopies(64,"a")),other=String.join("",java.util.Collections.nCopies(64,"b")),id="request-1234567890";
  byte[] audio="private-audio-do-not-store-plaintext".getBytes("UTF-8");long now=100000;
  try{
   EncryptedRecording.save(file,key,owner,id,audio,now);
   if(new String(Files.readAllBytes(file.toPath()),"ISO-8859-1").contains("private-audio"))throw new AssertionError("Plain audio leaked");
   EncryptedRecording.Entry entry=EncryptedRecording.read(file,key,owner,now+1000);
   if(!entry.id.equals(id)||!Arrays.equals(entry.audio,audio))throw new AssertionError("Round trip failed");
   if(EncryptedRecording.matches(file,owner,"different-request-123"))throw new AssertionError("Wrong request matched");
   byte[] corrupted=Files.readAllBytes(file.toPath());corrupted[corrupted.length-1]^=1;Files.write(file.toPath(),corrupted);
   try{EncryptedRecording.read(file,key,owner,now);throw new AssertionError("Tampered ciphertext accepted");}catch(javax.crypto.AEADBadTagException expected){}
   EncryptedRecording.save(file,key,owner,id,audio,now);
   if(EncryptedRecording.available(file,other,now)||file.exists())throw new AssertionError("Other session can access recording");
   EncryptedRecording.save(file,key,owner,id,audio,now);
   if(EncryptedRecording.available(file,owner,now+EncryptedRecording.TTL)||file.exists())throw new AssertionError("Expired recording retained");
   try{EncryptedRecording.save(file,key,owner,id,new byte[EncryptedRecording.MAX_BYTES+1],now);throw new AssertionError("Oversized recording accepted");}catch(java.io.IOException expected){}
   System.out.println("PASS: encrypted round trip, tamper detection, request isolation, session isolation, expiry, size bound");
  }finally{file.delete();Files.deleteIfExists(directory.resolve("recording.bin.tmp"));Files.delete(directory);}
 }
}
