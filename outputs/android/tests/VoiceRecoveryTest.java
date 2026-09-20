package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
/** Fault injection through a real HTTP server: retries read-only polls, never resends audio. */
public class VoiceRecoveryTest {
 public static void main(String[] args)throws Exception {
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  AtomicInteger polls=new AtomicInteger(),posts=new AtomicInteger();boolean[] denied={false};
  server.createContext("/v2/",exchange->{
   if(!exchange.getRequestMethod().equals("GET"))posts.incrementAndGet();
   String path=exchange.getRequestURI().getPath();int code=200;String body;
   if(path.endsWith("latest-dictation"))body="{\"id\":\"one-job\",\"state\":\"running\"}";
   else {int count=polls.incrementAndGet();if(denied[0]){code=401;body="{}";}else if(count==1){code=503;body="{}";}else body="{\"id\":\"one-job\",\"state\":\"done\",\"text\":\"recovered\"}";}
   byte[] bytes=body.getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(code,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
  });server.start();
  try {
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"test",false,"","",true,true);
   VoiceApi.Result result=VoiceApi.recover(config,VoiceApi.QUIET);
   if(!result.text.equals("recovered")||polls.get()!=2||posts.get()!=0)throw new AssertionError("Recovery retried incorrectly");
   denied[0]=true;polls.set(0);
   try{VoiceApi.recover(config,VoiceApi.QUIET);throw new AssertionError("401 must fail");}catch(VoiceApi.ApiError error){if(error.code!=401)throw error;}
   if(polls.get()!=1||posts.get()!=0)throw new AssertionError("Unauthorized poll retried");
   System.out.println("PASS: transient polling retry, no audio repost, and no retry after 401");
  }finally{server.stop(0);}
 }
}
