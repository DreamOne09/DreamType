package tw.localvoice.keyboard;
import java.security.*;
import java.security.spec.ECGenParameterSpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.json.JSONObject;

public class ServiceDiscoveryTest {
 static final long NOW=1800000000;
 static KeyPair key;
 interface Action {void run()throws Exception;}
 static void reject(Action action)throws Exception {try{action.run();}catch(Exception expected){return;}throw new AssertionError("Untrusted discovery accepted");}
 static JSONObject payload()throws Exception{return new JSONObject().put("service","dreamtype-home").put("url","https://fixture.trycloudflare.com").put("issued",NOW).put("expires",NOW+86400).put("serial",5);}
 static String signed(JSONObject payload)throws Exception {
  byte[] bytes=payload.toString().getBytes(StandardCharsets.UTF_8);
  Signature s=Signature.getInstance("SHA256withECDSA");s.initSign(key.getPrivate());s.update(bytes);
  return new JSONObject().put("payload",Base64.getEncoder().encodeToString(bytes)).put("signature",Base64.getEncoder().encodeToString(s.sign())).toString();
 }
 public static void main(String[] args)throws Exception {
  KeyPairGenerator generator=KeyPairGenerator.getInstance("EC");generator.initialize(new ECGenParameterSpec("secp256r1"));key=generator.generateKeyPair();byte[] pub=key.getPublic().getEncoded();
  String good=signed(payload());
  byte[] plain="signed metadata".getBytes(StandardCharsets.UTF_8);
  if(!ServiceDiscovery.readDocument(new java.io.ByteArrayInputStream(plain)).equals("signed metadata"))throw new AssertionError("Metadata read changed");
  reject(()->ServiceDiscovery.readDocument(new java.io.ByteArrayInputStream(new byte[10001])));
  reject(()->ServiceDiscovery.readDocument(new java.io.ByteArrayInputStream(new byte[]{(byte)0xc3,0x28})));
  if(!ServiceDiscovery.verify(good,pub,NOW,5).url.equals("https://fixture.trycloudflare.com"))throw new AssertionError("Valid discovery rejected");
  reject(()->ServiceDiscovery.verify(good,generator.generateKeyPair().getPublic().getEncoded(),NOW,0));
  reject(()->ServiceDiscovery.verify(good,pub,NOW+86400,0));
  reject(()->ServiceDiscovery.verify(good,pub,NOW-301,0));
  reject(()->ServiceDiscovery.verify(good,pub,NOW,6));
  JSONObject tampered=new JSONObject(good);tampered.put("payload",Base64.getEncoder().encodeToString(payload().put("url","https://hostile.trycloudflare.com").toString().getBytes(StandardCharsets.UTF_8)));
  reject(()->ServiceDiscovery.verify(tampered.toString(),pub,NOW,0));
  for(Object bad:new Object[]{true,"5",5.5,0,-1,9007199254740992L})reject(()->ServiceDiscovery.verify(signed(payload().put("serial",bad)),pub,NOW,0));
  reject(()->ServiceDiscovery.verify(signed(payload().put("token","forbidden")),pub,NOW,0));
  reject(()->ServiceDiscovery.verify(signed(payload().put("service","other")),pub,NOW,0));
  reject(()->ServiceDiscovery.verify(signed(payload().put("expires",NOW+86401)),pub,NOW,0));
  for(String url:new String[]{"http://fixture.trycloudflare.com","https://fixture.trycloudflare.com/","https://fixture.trycloudflare.com:443","https://user@fixture.trycloudflare.com","https://fixture.trycloudflare.com?key=x","https://dreamcube.tw","https://trycloudflare.com.evil.example","https://127.0.0.1"})reject(()->ServiceDiscovery.verify(signed(payload().put("url",url)),pub,NOW,0));
  // Python cryptography-generated public fixture; private key was never persisted.
  ServiceDiscovery.verify("{\"payload\":\"eyJleHBpcmVzIjoxODAwMDg2NDAwLCJpc3N1ZWQiOjE4MDAwMDAwMDAsInNlcmlhbCI6NSwic2VydmljZSI6ImRyZWFtdHlwZS1ob21lIiwidXJsIjoiaHR0cHM6Ly9maXh0dXJlLnRyeWNsb3VkZmxhcmUuY29tIn0=\",\"signature\":\"MEUCIQDIUgW3hjjd/rSw5Cp1U5E+d0d3nFsKqj2MvXMzhhMnVwIgPdPciXddoFWDBmcwOHDUn94KnRjRmeQTp62WYTu7yus=\"}",Base64.getDecoder().decode("MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE33lLn94hhIaxkLpsTem3oqYWxUwWa/ggZGaTZgEU8W797DSEfUhtQX0MzDHITqdeHLoG2WeZWm8g25OflDYzuw=="),NOW,5);
  System.out.println("PASS: signed service origins, tamper/wrong-key rejection, expiry and rollback protection");
 }
}
