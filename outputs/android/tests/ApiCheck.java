package tw.localvoice.keyboard;
import java.nio.file.*;
import java.io.File;
import org.json.JSONObject;

public class ApiCheck {
 public static void main(String[] args)throws Exception {
  JSONObject settings=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8"));
  String origin=settings.getString("url");
  if(!AppConfig.normalize(origin+"/v1/audio/transcriptions/").equals(origin))throw new Exception("URL normalization failed");
  for(String invalid:new String[]{"http://example.com","https://user@example.com","https://example.com/?key=secret","https://example.com/#fragment"}){
   boolean blocked=false;try{AppConfig.normalize(invalid);}catch(Exception e){blocked=true;}
   if(!blocked)throw new Exception("Unsafe URL accepted");
  }
  AppConfig config=new AppConfig(origin,settings.getString("key"),true);
  VoiceApi.verify(config);
  long start=System.nanoTime();VoiceApi.Result result=VoiceApi.upload(config,new File(args[1]));
  if(!result.text.contains("4")&&!result.text.contains("四"))throw new Exception("Unexpected transcription: "+result.text);
  System.out.println("Native Java HTTPS client passed: URL validation, authenticated model list, M4A upload, JSON parsing.");
  System.out.println("Transcription: "+result.text+"; wait: "+((System.nanoTime()-start)/1000000)+" ms");
 }
}
