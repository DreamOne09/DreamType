package tw.localvoice.keyboard;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;

/** Exercises the actual recover/receipt path; no native Android claims. */
public final class EmptyResultCheck {
 public static void main(String[] args)throws Exception {
  AtomicInteger receipts=new AtomicInteger();
  JSONObject[] response={new JSONObject()};
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v2/me/latest-dictation",exchange->{
   byte[] bytes=response[0].toString().getBytes("UTF-8");
   exchange.sendResponseHeaders(200,bytes.length);
   try(java.io.OutputStream out=exchange.getResponseBody()){out.write(bytes);}
  });
  server.createContext("/v2/dictations/test/receipt",exchange->{
   receipts.incrementAndGet();byte[] bytes="{}".getBytes("UTF-8");
   exchange.sendResponseHeaders(200,bytes.length);
   try(java.io.OutputStream out=exchange.getResponseBody()){out.write(bytes);}
  });
  server.start();
  try {
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic",false,"","",true,true);
   Object[] invalid={""," \n\t","\u3000\u00a0",JSONObject.NULL,123,new JSONObject()};
   for(Object text:invalid){
    response[0]=new JSONObject().put("state","done").put("id","test").put("receipt_required",true).put("text",text);
    try{VoiceApi.recover(config,VoiceApi.QUIET);throw new AssertionError("Invalid result accepted");}
    catch(java.io.IOException expected){}
    if(receipts.get()!=0)throw new AssertionError("Invalid result acknowledged");
   }
   response[0].put("text","明天到板橋拿文件。");
   if(!VoiceApi.recover(config,VoiceApi.QUIET).text.equals("明天到板橋拿文件。")||receipts.get()!=1)throw new AssertionError("Valid result not delivered");
   if(!VoiceApi.recover(config,VoiceApi.QUIET).rawText.isEmpty())throw new AssertionError("Missing original was invented");
   response[0].put("raw_text","明天到板橋拿文件");
   if(!VoiceApi.recover(config,VoiceApi.QUIET).rawText.equals("明天到板橋拿文件"))throw new AssertionError("Original transcript lost on recovery");
   response[0].put("raw_text",123);
   if(!VoiceApi.recover(config,VoiceApi.QUIET).rawText.isEmpty())throw new AssertionError("Invalid original accepted");
   System.out.println("PASS: six invalid results rejected before receipt; valid Chinese result acknowledged once.");
  }finally{server.stop(0);}
 }
}
