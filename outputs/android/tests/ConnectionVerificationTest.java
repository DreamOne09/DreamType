package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;

/** Actual private verify method with synthetic HTTP; no HTTPS setup/UI claims. */
public final class ConnectionVerificationTest {
 public static void main(String[] args)throws Exception {
  Path output=Paths.get(args[0]);if(Files.exists(output))throw new IllegalArgumentException("Evidence exists");
  String[] bodies={"{\"data\":null}","{\"data\":{}}","{\"data\":[]}","{\"data\":[{\"id\":123}]}","{\"data\":[{\"id\":\"local-dictation\"}]}"};
  String[] names={"null_data","object_data","empty_data","nonstring_id","valid_models"};
  AtomicInteger stage=new AtomicInteger(),requests=new AtomicInteger();
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v1/models",exchange->{
   requests.incrementAndGet();byte[] body=bodies[stage.get()].getBytes(StandardCharsets.UTF_8);
   try{exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);}finally{exchange.close();}
  });server.start();JSONObject cases=new JSONObject();boolean passed=true;
  try{
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic",false);
   for(int i=0;i<bodies.length;i++){
    stage.set(i);Exception failure=null;int before=requests.get();
    try{VoiceApi.verify(config);}catch(Exception error){failure=error;}
    boolean ok=(i==bodies.length-1?failure==null:failure instanceof java.io.IOException)&&requests.get()-before==1;
    cases.put(names[i],new JSONObject().put("passed",ok).put("success_reported",failure==null).put("requests",requests.get()-before));passed &= ok;
   }
  }finally{server.stop(0);}
  JSONObject report=new JSONObject().put("scope","Actual private VoiceApi.verify on JVM, synthetic HTTP; no setup Activity, saved settings, TLS or real key.").put("cases",cases).put("passed",passed);
  Files.write(output,report.toString(2).getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Connection verify: passed="+passed+"; evidence saved");if(!passed)throw new AssertionError("See evidence");
 }
}
