package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

/** Exercise transient and permanent receipt failures over HTTP. */
public final class ReceiptRecoveryTest {
 public static void main(String[] args)throws Exception {
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  AtomicInteger receipts=new AtomicInteger(),otherPosts=new AtomicInteger(),scenario=new AtomicInteger();
  server.createContext("/v2/",exchange->{
   int code=200;String body="{}";String path=exchange.getRequestURI().getPath();
   if(path.equals("/v2/me/latest-dictation"))body="{\"id\":\"receipt-job\",\"state\":\"done\",\"receipt_required\":true,\"text\":\"明天到板橋。\"}";
   else if(path.equals("/v2/dictations/receipt-job/receipt")&&exchange.getRequestMethod().equals("POST")){
    int count=receipts.incrementAndGet();
    if(scenario.get()==1)code=401;
    else if(scenario.get()==2||count==1)code=503;
   }else{otherPosts.incrementAndGet();code=400;}
   byte[] bytes=body.getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(code,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
  });server.start();
  try{
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic",false,"","",true,true);
   if(!VoiceApi.recover(config,VoiceApi.QUIET).text.equals("明天到板橋。")||receipts.get()!=2)throw new AssertionError("Receipt did not recover");
   scenario.set(1);receipts.set(0);
   try{VoiceApi.recover(config,VoiceApi.QUIET);throw new AssertionError("401 accepted");}catch(VoiceApi.ApiError error){if(error.code!=401)throw error;}
   if(receipts.get()!=1)throw new AssertionError("401 retried");
   scenario.set(2);receipts.set(0);
   try{VoiceApi.recover(config,VoiceApi.QUIET);throw new AssertionError("Unconfirmed text returned");}catch(VoiceApi.ApiError error){if(error.code!=503)throw error;}
   if(receipts.get()!=3||otherPosts.get()!=0)throw new AssertionError("Retry limit exceeded or audio reposted");
   System.out.println("PASS: receipt transient recovery, no retry after 401, bounded persistent failure, no audio repost");
  }finally{server.stop(0);}
 }
}
