package tw.localvoice.keyboard;
import org.json.*;
public final class UpdateCheckTest {
 static JSONObject release(String tag,boolean preview)throws Exception{
  String name="DreamType-"+UpdateCheck.core(tag)+".apk";
  return new JSONObject().put("tag_name",tag).put("prerelease",preview).put("assets",new JSONArray().put(new JSONObject().put("name",name).put("size",123).put("browser_download_url",UpdateCheck.REPO+"/releases/download/"+tag+"/"+name)));
 }
 public static void main(String[] args)throws Exception{
  JSONObject stable=release("v0.8.0",false),preview=release("v0.9.4-rc1",true);
  stable.getJSONArray("assets").getJSONObject(0).put("name","DreamType.apk").put("browser_download_url",UpdateCheck.REPO+"/releases/download/v0.8.0/DreamType.apk");
  JSONArray mixed=new JSONArray().put(preview).put(stable).put(release("v9.0.0",false).put("draft",true));
  if(!UpdateCheck.select(mixed,false).tag.equals("v0.8.0"))throw new AssertionError("Preview offered without opt in");
  UpdateCheck.Release selected=UpdateCheck.select(mixed,true);
  if(!selected.tag.equals("v0.9.4-rc1")||!selected.url.endsWith("/releases/tag/v0.9.4-rc1"))throw new AssertionError("Wrong preview or URL");
  if(!UpdateCheck.newer(selected.version,"0.9.3")||UpdateCheck.newer(selected.version,"0.9.4")||UpdateCheck.newer("0.8.0","0.9.4"))throw new AssertionError("Upgrade/downgrade comparison");
  if(!UpdateCheck.newer("0.10.0","0.9.9")||UpdateCheck.newer("bad","0.9.4")||UpdateCheck.newer("0.9.4","bad"))throw new AssertionError("Invalid version comparison");
  JSONObject foreign=release("v8.0.0",false);foreign.getJSONArray("assets").getJSONObject(0).put("browser_download_url","https://example.invalid/app.apk");
  mixed.put(foreign).put(release("v7.0.0",false).put("assets",new JSONArray())).put(release("v6.0.0-rc1",false));
  if(!UpdateCheck.select(mixed,false).tag.equals("v0.8.0"))throw new AssertionError("Unsafe or missing APK accepted");
  if(!UpdateCheck.select(new JSONArray().put(preview).put(release("v0.9.4",false)),true).tag.equals("v0.9.4"))throw new AssertionError("Stable tie not preferred");
  try{UpdateCheck.select(new JSONArray().put(foreign),true);throw new AssertionError("Invalid release accepted");}catch(java.io.IOException expected){}
  System.out.println("PASS: update opt in, exact release URL, numeric comparison, no downgrade, valid APK filtering");
 }
}
