package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.Arrays;
import java.util.concurrent.atomic.*;
import org.json.JSONObject;

/** Actual storage/API boundary; caller sequencing is explicit, not VoiceIme execution. */
public final class ReceiptPendingAudioTest {
 public static void main(String[] args)throws Exception {
  Path output=Paths.get(args[0]);if(Files.exists(output))throw new IllegalArgumentException("Evidence exists");
  if(Security.getProviders("KeyStore.AndroidKeyStore")!=null)throw new IllegalStateException("Existing Android provider");
  Provider provider=new Provider("DreamTypeReceiptSynthetic",1.0,"JVM-only synthetic key"){};
  provider.put("KeyStore.AndroidKeyStore",ConnectionPersistenceTest.SyntheticKeyStore.class.getName());Security.addProvider(provider);
  Path dir=Files.createTempDirectory("receipt-pending-contract-");
  AtomicInteger uploads=new AtomicInteger(),receipts=new AtomicInteger(),lookups=new AtomicInteger();
  AtomicBoolean failing=new AtomicBoolean(true);AtomicReference<String> id=new AtomicReference<>();
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v2/",exchange->{
   try{
    byte[] buffer=new byte[4096];while(exchange.getRequestBody().read(buffer)!=-1){}
    String path=exchange.getRequestURI().getPath();int status=200;JSONObject body;
    if(path.endsWith("/receipt")){receipts.incrementAndGet();status=failing.get()?503:200;body=new JSONObject().put("ok",!failing.get());}
    else {
     if(exchange.getRequestMethod().equals("POST")){uploads.incrementAndGet();id.set(exchange.getRequestHeaders().getFirst("Idempotency-Key"));}
     else lookups.incrementAndGet();
     body=new JSONObject().put("id",id.get()).put("state","done").put("receipt_required",true).put("text","合成保留文字。").put("raw_text","合成保留文字");
    }
    byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);exchange.sendResponseHeaders(status,bytes.length);exchange.getResponseBody().write(bytes);
   }finally{exchange.close();}
  });server.start();JSONObject checks=new JSONObject();
  try{
   ConnectionPersistenceTest.Ctx context=new ConnectionPersistenceTest.Ctx(dir);
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"synthetic-receipt-token",false,"","",true,true);
   config.save(context);
   byte[] audio="synthetic-audio-only".getBytes(StandardCharsets.UTF_8);Path source=dir.resolve("source.bin");Files.write(source,audio);
   EncryptedRecording.Entry saved=PendingAudio.prepare(context,config,source.toFile());
   Path encrypted=dir.resolve("pending-recording.bin");byte[] original=Files.readAllBytes(encrypted);
   // Explicitly remove only the test input after prepare: prove retained audio
   // is independent of it. This is not an execution of VoiceIme's finally block.
   Files.delete(source);
   VoiceApi.Result received=null;Exception failure=null;
   try{received=VoiceApi.upload(saved.requestConfig(config),saved.audio,saved.id,VoiceApi.QUIET,false);}
   catch(Exception error){failure=error;}
   checks.put("failed_receipt_no_result",failure instanceof VoiceApi.ApiError&&((VoiceApi.ApiError)failure).code==503&&received==null);
   checks.put("one_upload_three_receipts",uploads.get()==1&&receipts.get()==3);
   checks.put("encrypted_file_unchanged_after_failure",Arrays.equals(original,Files.readAllBytes(encrypted)));
   EncryptedRecording.Entry retry=PendingAudio.read(context,config);
   checks.put("retained_request_and_audio_readable",saved.id.equals(retry.id)&&Arrays.equals(audio,retry.audio));
   failing.set(false);
   VoiceApi.Result recovered=VoiceApi.recover(config,VoiceApi.QUIET);
   checks.put("recovery_confirmed_without_upload",saved.id.equals(recovered.id)&&recovered.text.equals("合成保留文字。")&&uploads.get()==1&&receipts.get()==4&&lookups.get()==1);
   checks.put("api_does_not_erase_recording",Files.exists(encrypted));
   PendingAudio.clearIfRequest(context,config,recovered.id);
   checks.put("matching_confirmed_result_can_clear",!Files.exists(encrypted));
  }finally{server.stop(0);Security.removeProvider(provider.getName());Files.deleteIfExists(dir.resolve("source.bin"));Files.deleteIfExists(dir.resolve("pending-recording.bin"));Files.deleteIfExists(dir.resolve("pending-recording.bin.tmp"));Files.delete(dir);}
  boolean passed=true;for(String name:checks.keySet())passed &= checks.getBoolean(name);
  JSONObject report=new JSONObject().put("scope","Actual PendingAudio prepare/read/clearIfRequest and VoiceApi upload/recover on JVM with synthetic AndroidKeyStore/Context and HTTP; explicit caller sequencing, not VoiceIme/UI/TLS.")
    .put("checks",checks).put("passed",passed).put("uploads",uploads.get()).put("receipts",receipts.get()).put("lookups",lookups.get())
    .put("temporary_state_removed",!Files.exists(dir)).put("synthetic_provider_removed",Security.getProvider(provider.getName())==null);
  Files.write(output,report.toString(2).getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Receipt/storage boundary: passed="+passed+"; evidence saved");if(!passed)throw new AssertionError("See evidence");
 }
}
