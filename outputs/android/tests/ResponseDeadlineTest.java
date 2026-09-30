package tw.localvoice.keyboard;
import java.io.*;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;

public class ResponseDeadlineTest {
 public static void main(String[] args)throws Exception {
  String value=VoiceApi.readBounded(new ByteArrayInputStream("正常".getBytes(StandardCharsets.UTF_8)),1000000000L);
  if(!value.equals("正常"))throw new AssertionError("Fast response changed");
  for(boolean eof:new boolean[]{false,true}) {
   boolean[] closed={false};
   InputStream slow=new InputStream(){
    public int read(){throw new AssertionError("Use block read");}
    public int read(byte[] b,int off,int len)throws IOException {
     try{Thread.sleep(30);}catch(InterruptedException e){throw new IOException(e);}
     b[off]=' ';return eof?-1:1;
    }
    public void close(){closed[0]=true;}
   };
   try{VoiceApi.readBounded(slow,10000000L);throw new AssertionError("Late body accepted");}
   catch(SocketTimeoutException expected){}
   if(!closed[0])throw new AssertionError("Timed-out stream not closed");
  }
  try{VoiceApi.readBounded(new ByteArrayInputStream(new byte[1024*1024+1]),1000000000L);throw new AssertionError("Oversize accepted");}
  catch(IOException expected){if(!expected.getMessage().equals("回應太長。"))throw expected;}
  System.out.println("PASS: body elapsed deadline, late EOF rejection, close and size bound");
 }
}
