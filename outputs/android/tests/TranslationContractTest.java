package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicInteger;
public class TranslationContractTest {
 public static void main(String[] args)throws Exception {
  AppConfig original=new AppConfig("https://first.invalid","key",false,"","",true,true,"translate","ja","zh-TW");
  AppConfig changedLanguage=new AppConfig("https://first.invalid","key",false,"","",true,true,"translate","th","zh-TW");
  if(!original.sameSession(changedLanguage)||!original.targetLanguage.equals("ja"))throw new AssertionError("Recording snapshot changed with preferences");
  if(original.sameSession(new AppConfig("https://second.invalid","key",false,"","",true,true)))throw new AssertionError("Different host accepted");
  if(original.sameSession(new AppConfig("https://first.invalid","other",false,"","",true,true)))throw new AssertionError("Different login accepted");
  if(original.sameSession(new AppConfig("https://first.invalid","key",false)))throw new AssertionError("Different authorization mode accepted");
  if(original.sameSession(null))throw new AssertionError("Missing session accepted");
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);AtomicInteger receipts=new AtomicInteger();int[] stage={0};
  server.createContext("/v2/",e->{
   String body;
   if(e.getRequestURI().getPath().endsWith("/receipt")){receipts.incrementAndGet();body="{\"ok\":true}";}
   else {
    if(!"translate".equals(e.getRequestHeaders().getFirst("X-DreamType-Mode"))||!"ja".equals(e.getRequestHeaders().getFirst("X-DreamType-Target")))throw new AssertionError("Missing mode headers");
    body="{\"id\":\"test-job\",\"state\":\"done\",\"text\":\"hello\",\"receipt_required\":true"+(stage[0]==0?"":",\"mode\":\"translate\",\"target_language\":\""+(stage[0]==1?"ja":"th")+"\"")+"}";
   }
   byte[] b=body.getBytes(StandardCharsets.UTF_8);e.sendResponseHeaders(200,b.length);e.getResponseBody().write(b);e.close();
  });server.start();
  try {
   AppConfig c=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"test",false,"","",true,true,"translate","ja","zh-TW");
   for(int i=0;i<3;i++){
    stage[0]=i;
    try{VoiceApi.Result r=VoiceApi.upload(c,new byte[]{1},"request-123456789",VoiceApi.QUIET,i==2);if(i!=1||!r.targetLanguage.equals("ja"))throw new AssertionError("Wrong translation accepted");}
    catch(IOException ex){if(i==1||!ex.getMessage().contains("0.8.0"))throw ex;}
   }
   if(receipts.get()!=1)throw new AssertionError("An invalid result was acknowledged");
   System.out.println("PASS: language headers, legacy/mismatched result rejection and receipt after validation");
  }finally{server.stop(0);}
 }
}
