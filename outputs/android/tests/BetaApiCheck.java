package tw.localvoice.keyboard;
import java.nio.file.*;
import java.io.File;
import org.json.JSONObject;
/** Host-JVM contract test of the exact API class packaged in the APK; not an Android UI test. */
public class BetaApiCheck {
 public static void main(String[] args)throws Exception {
  JSONObject input=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8"));
  String host=AppConfig.normalize(input.getString("server"));String pass=input.getString("password");
  JSONObject login=VoiceApi.json(new AppConfig(host,"",false),"POST","/v2/login",new JSONObject().put("username",input.getString("username")).put("password",pass));
  AppConfig config=new AppConfig(host,login.getString("token"),false,"","",true,true);
  try{
   VoiceApi.verify(config);
   VoiceApi.json(config,"POST","/v2/me/preferences",new JSONObject().put("personal_prompt","使用完整句子，保留正確時間。"));
   String requestId=java.util.UUID.randomUUID().toString();byte[] audio=Files.readAllBytes(Paths.get(args[1]));
   long start=System.nanoTime();VoiceApi.Result result=VoiceApi.upload(config,audio,requestId,VoiceApi.QUIET,false);
   if(result.text.trim().isEmpty()||!result.warning.isEmpty())throw new Exception("No successful formatted result");
   JSONObject me=VoiceApi.json(config,"GET","/v2/me",null);if(me.getInt("used_seconds")<=0)throw new Exception("Usage not charged");
   VoiceApi.Result recovered=VoiceApi.recover(config,VoiceApi.QUIET);
   if(!result.text.equals(recovered.text))throw new Exception("Recovered result mismatch");
   if(me.getInt("used_seconds")!=VoiceApi.json(config,"GET","/v2/me",null).getInt("used_seconds"))throw new Exception("Recovery charged twice");
   VoiceApi.json(config,"POST","/v2/me/preferences",new JSONObject().put("personal_prompt","新錄音才改用條列"));
   VoiceApi.Result retried=VoiceApi.upload(config,audio,requestId,VoiceApi.QUIET,true);
   if(!result.text.equals(retried.text)||me.getInt("used_seconds")!=VoiceApi.json(config,"GET","/v2/me",null).getInt("used_seconds"))throw new Exception("Retry changed result or charged twice");
   System.out.println(new JSONObject().put("https_login",true).put("preferences",true).put("queued_upload",true).put("usage",true).put("total_seconds",(System.nanoTime()-start)/1e9).put("native_device_test",false));
  }finally{VoiceApi.json(config,"DELETE","/v2/me",new JSONObject().put("password",pass));}
 }
}
