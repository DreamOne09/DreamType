package tw.localvoice.keyboard;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

public final class ErrorMessageTest {
 public static void main(String[] args)throws Exception {
  int[] status={429};String[] body={""};
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/v2/test",e->{byte[] data=body[0].getBytes(StandardCharsets.UTF_8);e.sendResponseHeaders(status[0],data.length);e.getResponseBody().write(data);e.close();});
  server.start();
  try{
   AppConfig config=new AppConfig("http://127.0.0.1:"+server.getAddress().getPort(),"test",false);
   String[][] cases={{"409","result_unconfirmed","取回上一筆"},{"429","queue_full","未扣額度"},{"429","job_in_progress","上一段仍在處理"},{"429","auth_rate_limit","一分鐘"},{"429","unknown","服務忙碌"},{"409","queue_full","請求衝突"}};
   for(String[] item:cases){
    status[0]=Integer.parseInt(item[0]);body[0]="{\"error_code\":\""+item[1]+"\",\"detail\":\"untrusted-detail\"}";
    try{VoiceApi.json(config,"GET","/v2/test",null);throw new AssertionError("Error accepted");}
    catch(VoiceApi.ApiError error){if(error.code!=status[0]||!error.getMessage().contains(item[2])||error.getMessage().contains("untrusted-detail"))throw new AssertionError("Incorrect error guidance");}
   }
   body[0]="<html>untrusted-detail</html>";status[0]=429;
   try{VoiceApi.json(config,"GET","/v2/test",null);throw new AssertionError("Proxy error accepted");}
   catch(VoiceApi.ApiError error){if(!error.getMessage().contains("服務忙碌"))throw error;}
   System.out.println("PASS: actionable known errors, status matching and safe unknown/proxy fallback");
  }finally{server.stop(0);}
 }
}
