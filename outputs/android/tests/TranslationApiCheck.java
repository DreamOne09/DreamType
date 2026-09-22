package tw.localvoice.keyboard;
import java.nio.file.*;
import org.json.*;
/** Exact APK networking class against a real host. No native UI/Keystore claim. */
public class TranslationApiCheck {
 public static void main(String[] args)throws Exception {
  JSONObject input=new JSONObject(new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8"));
  String host=AppConfig.normalize(input.getString("server")),password=input.getString("password");
  JSONObject session=VoiceApi.json(new AppConfig(host,"",false),"POST","/v2/login",new JSONObject().put("username",input.getString("username")).put("password",password));
  AppConfig base=new AppConfig(host,session.getString("token"),false,"","",true,true);
  JSONArray results=new JSONArray();byte[] audio=Files.readAllBytes(Paths.get(args[1]));
  try{
   for(String target:AppConfig.LANGUAGE_CODES){
    AppConfig config=new AppConfig(host,base.key,false,"","",true,true,"translate",target,"zh-TW");
    String id=java.util.UUID.randomUUID().toString();long start=System.nanoTime();
    VoiceApi.Result result=VoiceApi.upload(config,audio,id,VoiceApi.QUIET,false);
    JSONObject latest=VoiceApi.json(config,"GET","/v2/me/latest-dictation",null);
    if(!"translate".equals(latest.getString("mode"))||!target.equals(latest.getString("target_language"))||latest.getBoolean("receipt_required")||result.text.trim().isEmpty())throw new Exception("Translation contract failed: "+target);
    int used=VoiceApi.json(config,"GET","/v2/me",null).getInt("used_seconds");
    VoiceApi.Result again=VoiceApi.upload(config,audio,id,VoiceApi.QUIET,true);
    if(!again.text.equals(result.text)||used!=VoiceApi.json(config,"GET","/v2/me",null).getInt("used_seconds"))throw new Exception("Translation retry changed result or quota");
    results.put(new JSONObject().put("target",target).put("seconds",(System.nanoTime()-start)/1e9).put("receipt_confirmed",true).put("retry_no_double_charge",true));
   }
   System.out.println(new JSONObject().put("https_translation",true).put("languages",results).put("native_device_test",false));
  }finally{VoiceApi.json(base,"DELETE","/v2/me",new JSONObject().put("password",password));}
 }
}
