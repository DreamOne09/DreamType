package tw.localvoice.keyboard;
import java.net.*;
import java.io.*;
import org.json.JSONObject;
final class UpdateCheck {
 static String latest()throws Exception{
  HttpURLConnection c=(HttpURLConnection)new URL("https://api.github.com/repos/DreamOne09/DreamType/releases/latest").openConnection();
  c.setConnectTimeout(10000);c.setReadTimeout(10000);c.setRequestProperty("Accept","application/vnd.github+json");c.setRequestProperty("User-Agent","DreamType-Android");
  try{if(c.getResponseCode()!=200)throw new IOException("Update check unavailable");try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){out.write(b,0,n);if(out.size()>262144)throw new IOException("Response too large");}JSONObject release=new JSONObject(out.toString("UTF-8"));if(release.optBoolean("draft")||release.optBoolean("prerelease"))throw new IOException("No stable release");return release.getString("tag_name");}}finally{c.disconnect();}
 }
 static boolean newer(String available,String current){
  String a=available.replaceFirst("^v","");if(!a.matches("[0-9]+\\.[0-9]+\\.[0-9]+"))return false;
  String[] x=a.split("\\."),y=current.replaceFirst("^v","").split("\\.");
  try{for(int i=0;i<3;i++){int delta=Integer.compare(Integer.parseInt(x[i]),Integer.parseInt(y[i]));if(delta!=0)return delta>0;}}catch(Exception ignored){}return false;
 }
}
