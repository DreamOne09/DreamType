package tw.localvoice.keyboard;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;

/** Actual private VoiceApi upload over controlled HTTP. Not HTTPS/UI/Keystore validation. */
public final class UploadResponseFailureTest {
 public static void main(String[] args)throws Exception {
  Path report=Paths.get(args[0]);
  if(Files.exists(report))throw new IllegalArgumentException("Preserve earlier evidence");
  AtomicInteger scenario=new AtomicInteger(),posts=new AtomicInteger();
  byte[] input="synthetic-recording-no-private-audio".getBytes(StandardCharsets.UTF_8);
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v1/audio/transcriptions",exchange->{
   posts.incrementAndGet();
   try {
    // Drain the actual multipart upload before injecting a response failure.
    byte[] buffer=new byte[4096];while(exchange.getRequestBody().read(buffer)!=-1){}
    byte[] body;
    if(scenario.get()==0)body="{\"text\":\"前一筆成功文字。\",\"raw_text\":\"前一筆成功文字\"}".getBytes(StandardCharsets.UTF_8);
    else if(scenario.get()==1)body="{\"text\":\"截斷".getBytes(StandardCharsets.UTF_8);
    else {
     byte[] prefix="{\"text\":\"".getBytes(StandardCharsets.UTF_8),suffix="\"}".getBytes(StandardCharsets.UTF_8);
     body=new byte[prefix.length+2+suffix.length];
     System.arraycopy(prefix,0,body,0,prefix.length);
     body[prefix.length]=(byte)0xe4;body[prefix.length+1]=(byte)0xb8;
     System.arraycopy(suffix,0,body,prefix.length+2,suffix.length);
    }
    exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);
   }finally{exchange.close();}
  });
  server.start();
  Path audio=Files.createTempFile("dreamtype-upload-contract-",".bin");
  JSONObject result=new JSONObject().put("scope","Actual private VoiceApi.upload on host JVM; synthetic recording and controlled HTTP. No Android UI, HTTPS or encrypted retry-buffer claim.");
  JSONObject checks=new JSONObject(),observations=new JSONObject();
  try {
   Files.write(audio,input);
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic",false);
   VoiceApi.Result first=VoiceApi.upload(config,audio.toFile());
   checks.put("valid_control",first.text.equals("前一筆成功文字。"));
   for(int i=1;i<=2;i++){
    scenario.set(i);int before=posts.get();VoiceApi.Result received=null;Exception failure=null;
    try{received=VoiceApi.upload(config,audio.toFile());}catch(Exception error){failure=error;}
    String name=i==1?"truncated_json":"invalid_utf8";
    checks.put(name+"_rejected",failure!=null&&received==null);
    checks.put(name+"_single_upload",posts.get()-before==1);
    checks.put(name+"_input_file_unchanged",Arrays.equals(input,Files.readAllBytes(audio)));
    observations.put(name,new JSONObject().put("failure_type",failure==null?JSONObject.NULL:failure.getClass().getSimpleName())
       .put("returned_text",received==null?JSONObject.NULL:received.text));
   }
  }finally{server.stop(0);Files.deleteIfExists(audio);}
  boolean passed=true;for(java.util.Iterator<String> it=checks.keys();it.hasNext();)passed &= checks.getBoolean(it.next());
  result.put("checks",checks).put("observations",observations).put("posts",posts.get()).put("passed",passed)
        .put("temporary_audio_removed",!Files.exists(audio));
  Files.write(report,result.toString(2).getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Upload response contract: passed="+passed+", posts="+posts.get()+"; report saved");
  if(!passed)throw new AssertionError("See saved response failure evidence");
 }
}
