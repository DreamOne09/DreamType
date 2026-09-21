package tw.localvoice.keyboard;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** One bounded, authenticated recording. No Android dependency so storage failures can be tested. */
final class EncryptedRecording {
 static final int MAX_BYTES=2*1024*1024;
 static final long TTL=60*60*1000L;
 static final class Entry {
  final String id;final byte[] audio;
  Entry(String id,byte[] audio){this.id=id;this.audio=audio;}
 }
 private static String[] header(DataInputStream in)throws Exception{
  String[] parts=in.readUTF().split("\\|",-1);
  if(parts.length!=4||!parts[0].equals("DT1")||!parts[3].matches("[A-Za-z0-9_-]{16,80}"))throw new IOException("Invalid recording header");
  return parts;
 }
 static boolean available(File file,String owner,long now){
  if(!file.exists())return false;
  try(DataInputStream in=new DataInputStream(new FileInputStream(file))){
   String[] h=header(in);long expiry=Long.parseLong(h[1]);
   if(h[2].equals(owner)&&expiry>now&&expiry-now<=TTL&&file.length()<=MAX_BYTES+1024)return true;
  }catch(Exception ignored){}
  file.delete();return false;
 }
 static boolean matches(File file,String owner,String id){
  try(DataInputStream in=new DataInputStream(new FileInputStream(file))){String[] h=header(in);return h[2].equals(owner)&&h[3].equals(id);}catch(Exception e){return false;}
 }
 static void save(File file,SecretKey key,String owner,String id,byte[] audio,long now)throws Exception{
  if(audio.length==0||audio.length>MAX_BYTES||!id.matches("[A-Za-z0-9_-]{16,80}")||!owner.matches("[a-f0-9]{64}"))throw new IOException("Invalid recording");
  String header="DT1|"+(now+TTL)+"|"+owner+"|"+id;
  Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key);cipher.updateAAD(header.getBytes(StandardCharsets.UTF_8));
  byte[] encrypted=cipher.doFinal(audio),iv=cipher.getIV();File temporary=new File(file.getPath()+".tmp");
  try{
   try(FileOutputStream stream=new FileOutputStream(temporary);DataOutputStream out=new DataOutputStream(stream)){
    out.writeUTF(header);out.writeInt(iv.length);out.write(iv);out.write(encrypted);out.flush();stream.getFD().sync();
   }
   Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
  }finally{temporary.delete();}
 }
 static Entry read(File file,SecretKey key,String owner,long now)throws Exception{
  if(!available(file,owner,now))throw new IOException("沒有可重試的錄音，或保留時間已到。");
  try(DataInputStream in=new DataInputStream(new FileInputStream(file))){
   String[] h=header(in);int n=in.readInt();if(n!=12)throw new IOException("Invalid recording nonce");
   byte[] iv=new byte[n];in.readFully(iv);ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int count;
   while((count=in.read(buffer))!=-1){out.write(buffer,0,count);if(out.size()>MAX_BYTES+16)throw new IOException("Recording too large");}
   Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,iv));cipher.updateAAD(String.join("|",h).getBytes(StandardCharsets.UTF_8));
   return new Entry(h[3],cipher.doFinal(out.toByteArray()));
  }
 }
}
