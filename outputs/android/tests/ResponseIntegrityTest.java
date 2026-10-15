package tw.localvoice.keyboard;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;

/** Existing low-level HTTP test entry; does not exercise or bypass HTTPS login UI. */
public final class ResponseIntegrityTest {
 static final String ID="integrity-request-0001";
 public static void main(String[] args)throws Exception {
  Path output=Paths.get(args[0]);if(Files.exists(output))throw new IllegalArgumentException("Evidence exists");
  AtomicInteger stage=new AtomicInteger(),uploads=new AtomicInteger(),polls=new AtomicInteger(),receipts=new AtomicInteger();
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/",exchange->{
   try {
    byte[] buffer=new byte[4096];while(exchange.getRequestBody().read(buffer)!=-1){}
    String path=exchange.getRequestURI().getPath();JSONObject body=new JSONObject();
    if(path.endsWith("/receipt")){
     receipts.incrementAndGet();
     if(stage.get()==5)body.put("ok",false);
     else if(stage.get()==6)body.put("ok","true");
     else if(stage.get()==7)body.put("ok",JSONObject.NULL);
     else if(stage.get()!=8)body.put("ok",true);
    }else{
     boolean post=exchange.getRequestMethod().equals("POST");
     if(post)uploads.incrementAndGet();else polls.incrementAndGet();
     body.put("state",stage.get()==2&&post?"running":"done").put("id",ID)
         .put("text","這一筆合成文字。").put("raw_text","這一筆合成文字").put("receipt_required",true);
     if(stage.get()==1||(stage.get()==2&&!post))body.put("id","different-request-0002");
     if(stage.get()==3)body.remove("id");
     if(stage.get()==4)body.put("id",123);
     if(stage.get()==9)body.put("receipt_required","false");
    }
    byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);
    if(stage.get()==10){bytes=new byte[1024*1024+1];java.util.Arrays.fill(bytes,(byte)' ');}
    exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);
   }catch(java.io.IOException closed){}finally{exchange.close();}
  });server.start();
  String[] names={"valid_control","wrong_initial_job","wrong_polled_job","missing_job","numeric_job",
                  "receipt_false","receipt_string_true","receipt_null","receipt_missing","receipt_flag_wrong_type","oversize_http_body"};
  JSONObject cases=new JSONObject();boolean passed=true;
  try{
   String host="http://127.0.0.1:"+server.getAddress().getPort();
   AppConfig account=new AppConfig(host,"synthetic",false,"","",true,true);
   AppConfig privateConfig=new AppConfig(host,"synthetic",false);
   for(int i=0;i<names.length;i++){
    stage.set(i);uploads.set(0);polls.set(0);receipts.set(0);
    VoiceApi.Result value=null;Exception failure=null;
    try{value=VoiceApi.upload(i==10?privateConfig:account,new byte[]{1,2,3},ID,VoiceApi.QUIET,false);}
    catch(Exception error){failure=error;}
    boolean ok=i==0?failure==null&&value!=null&&ID.equals(value.id)&&receipts.get()==1:failure!=null&&value==null;
    ok &= uploads.get()==1;
    if((i>=1&&i<=4)||i==9||i==10)ok &= receipts.get()==0;
    cases.put(names[i],new JSONObject().put("passed",ok).put("uploads",uploads.get()).put("polls",polls.get())
      .put("receipts",receipts.get()).put("failure_type",failure==null?JSONObject.NULL:failure.getClass().getSimpleName())
      .put("result_returned",value!=null));
    passed &= ok;
   }
  }finally{server.stop(0);}
  JSONObject report=new JSONObject().put("scope","Host JVM actual VoiceApi low-level HTTP; synthetic only; not Android HTTPS/UI/Keystore.")
      .put("cases",cases).put("passed",passed);
  Files.write(output,report.toString(2).getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Response integrity: "+names.length+" cases, passed="+passed+"; report saved");
  if(!passed)throw new AssertionError("See response integrity evidence");
 }
}
