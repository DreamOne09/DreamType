package tw.localvoice.keyboard;
import java.io.*;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;

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
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v2/me",exchange->{
   try {
    exchange.sendResponseHeaders(200,0);
    OutputStream stream=exchange.getResponseBody();stream.write('{');stream.flush();
    for(int i=0;i<170;i++){Thread.sleep(100);stream.write(' ');stream.flush();}
    stream.write('}');
   }catch(Exception ignored){}finally{exchange.close();}
  });
  server.start();
  try {
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic",false,"","",true,true);
   try{VoiceApi.json(config,"GET","/v2/me",null);throw new AssertionError("Trickling HTTP body accepted");}
   catch(SocketTimeoutException expected){}
  }finally{server.stop(0);}
  System.out.println("PASS: body elapsed deadline, late EOF rejection, close, size bound and trickling HTTP");
 }
}
