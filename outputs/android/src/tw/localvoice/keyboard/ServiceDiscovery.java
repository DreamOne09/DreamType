package tw.localvoice.keyboard;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import org.json.JSONObject;

/** Public signed metadata only. Never receives account credentials. */
final class ServiceDiscovery {
 static final String DOCUMENT="https://raw.githubusercontent.com/DreamOne09/DreamType/service-discovery/endpoint.json";
 static final String PUBLIC_KEY="MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEcAt3xHIK2Xg2zO5vlkasTPuCADBf+DetOoLilmgc8+O1KIDabrEyDOABf2xXBvZW3TbXNhykl9kfoFft0k+g1Q==";
 static final long MAX_SERIAL=9007199254740991L;
 static Endpoint fetch(long minimumSerial)throws Exception {
  java.net.HttpURLConnection connection=(java.net.HttpURLConnection)new java.net.URL(DOCUMENT).openConnection();
  connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(5000);connection.setReadTimeout(5000);
  connection.setRequestProperty("User-Agent","DreamType-Android");connection.setRequestProperty("Accept","application/json");
  try {
   if(connection.getResponseCode()!=200)throw new IOException("Discovery unavailable");
   return verify(readDocument(connection.getInputStream()),Base64.getDecoder().decode(PUBLIC_KEY),System.currentTimeMillis()/1000,minimumSerial);
  } finally {connection.disconnect();}
 }
 static String readDocument(java.io.InputStream source)throws Exception {
  long start=System.nanoTime();
  try(java.io.InputStream in=source;java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()){
   byte[] buffer=new byte[1024];int count;
   while(true){
    if(System.nanoTime()-start>5000000000L)throw new java.net.SocketTimeoutException("Discovery deadline");
    count=in.read(buffer);
    if(System.nanoTime()-start>5000000000L)throw new java.net.SocketTimeoutException("Discovery deadline");
    if(count==-1)break;
    if(out.size()+count>10000)throw new IOException("Oversized discovery response");
    out.write(buffer,0,count);
   }
   return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(out.toByteArray())).toString();
  }
 }
 static final class Endpoint {
  final String url;final long serial,expires;
  Endpoint(String url,long serial,long expires){this.url=url;this.serial=serial;this.expires=expires;}
 }
 static String origin(String value)throws IOException {
  if(value==null||value.length()>253||!value.matches("https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.(?:trycloudflare\\.com|dreamone\\.li)"))throw new IOException("Invalid service origin");
  return value;
 }
 private static long number(JSONObject value,String name)throws Exception {
  Object n=value.get(name);
  if(!(n instanceof Integer)&&!(n instanceof Long))throw new IOException("Invalid discovery number");
  long result=((Number)n).longValue();
  if(result<0||result>MAX_SERIAL)throw new IOException("Discovery number out of range");
  return result;
 }
 static Endpoint verify(String envelope,byte[] publicDer,long now,long minimumSerial)throws Exception {
  if(envelope==null||envelope.length()>10000)throw new IOException("Oversized discovery response");
  JSONObject outer=new JSONObject(envelope);
  if(outer.length()!=2||!(outer.get("payload") instanceof String)||!(outer.get("signature") instanceof String))throw new IOException("Invalid discovery envelope");
  String body=outer.getString("payload"),signature=outer.getString("signature");
  if(body.length()>4096||signature.length()>128)throw new IOException("Oversized discovery fields");
  byte[] raw=Base64.getDecoder().decode(body),sig=Base64.getDecoder().decode(signature);
  Signature verifier=Signature.getInstance("SHA256withECDSA");
  verifier.initVerify(KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(publicDer)));
  verifier.update(raw);
  if(!verifier.verify(sig))throw new IOException("Invalid discovery signature");
  String text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
  JSONObject value=new JSONObject(text);
  if(value.length()!=5||!"dreamtype-home".equals(value.get("service"))||!(value.get("url") instanceof String))throw new IOException("Wrong discovery service");
  long issued=number(value,"issued"),expires=number(value,"expires"),serial=number(value,"serial");
  if(serial<1||serial<minimumSerial||issued>now+300||expires<=now||expires<=issued||expires-issued>86400)throw new IOException("Expired or stale discovery metadata");
  return new Endpoint(origin(value.getString("url")),serial,expires);
 }
}
