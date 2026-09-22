package tw.localvoice.keyboard;
import java.net.*;
import java.io.*;
import org.json.JSONObject;
import org.json.JSONArray;
final class UpdateCheck {
 static final String REPO="https://github.com/DreamOne09/DreamType";
 static final class Release {
  final String tag,version,url;final boolean preview;
  Release(String tag,boolean preview){this.tag=tag;this.version=core(tag);this.preview=preview;this.url=REPO+"/releases/tag/"+tag;}
 }
 static Release latest(boolean previews)throws Exception{
  String endpoint="https://api.github.com/repos/DreamOne09/DreamType/releases"+(previews?"?per_page=100":"/latest");
  HttpURLConnection c=(HttpURLConnection)new URL(endpoint).openConnection();
  c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(10000);c.setRequestProperty("Accept","application/vnd.github+json");c.setRequestProperty("User-Agent","DreamType-Android");
  try{if(c.getResponseCode()!=200)throw new IOException("Update check unavailable");try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
   byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>2097152)throw new IOException("Response too large");}
   String body=out.toString("UTF-8");return select(previews?new JSONArray(body):new JSONArray().put(new JSONObject(body)),previews);
  }}finally{c.disconnect();}
 }
 static String core(String tag){return tag.replaceFirst("^v","").replaceFirst("-rc[0-9]+$","");}
 static Release select(JSONArray releases,boolean previews)throws Exception{
  Release best=null;
  for(int i=0;i<releases.length();i++){
   JSONObject item=releases.optJSONObject(i);if(item==null||item.optBoolean("draft"))continue;
   String tag=item.optString("tag_name","");if(!tag.matches("v?[0-9]+\\.[0-9]+\\.[0-9]+(-rc[0-9]+)?"))continue;
   boolean preview=item.optBoolean("prerelease")||tag.contains("-rc");if(preview&&!previews)continue;
   String name="DreamType-"+core(tag)+".apk";
   JSONArray assets=item.optJSONArray("assets");boolean apk=false;
   if(assets!=null)for(int j=0;j<assets.length();j++){JSONObject asset=assets.optJSONObject(j);if(asset==null)continue;String actual=asset.optString("name");String expected=REPO+"/releases/download/"+tag+"/"+actual;if((name.equals(actual)||"DreamType.apk".equals(actual))&&expected.equals(asset.optString("browser_download_url"))&&asset.optLong("size",0)>0)apk=true;}
   if(!apk)continue;
   Release candidate=new Release(tag,preview);
   if(best==null||newer(candidate.version,best.version)||(candidate.version.equals(best.version)&&best.preview&&!candidate.preview))best=candidate;
  }
  if(best==null)throw new IOException("No installable release");return best;
 }
 static boolean newer(String available,String current){
  String a=core(available),b=core(current);if(!a.matches("[0-9]+\\.[0-9]+\\.[0-9]+")||!b.matches("[0-9]+\\.[0-9]+\\.[0-9]+"))return false;
  String[] x=a.split("\\."),y=b.split("\\.");
  for(int i=0;i<3;i++){int delta=new java.math.BigInteger(x[i]).compareTo(new java.math.BigInteger(y[i]));if(delta!=0)return delta>0;}return false;
 }
}
