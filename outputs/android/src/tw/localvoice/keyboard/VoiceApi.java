package tw.localvoice.keyboard;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.JSONObject;

final class VoiceApi {
    static final class Result {
        final String text,warning;
        final double computerSeconds;
        Result(String t,String w,double s){text=t;warning=w;computerSeconds=s;}
    }
    private static HttpURLConnection connection(AppConfig config,String path) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(config.server+path).openConnection();
        c.setInstanceFollowRedirects(false); c.setConnectTimeout(15000); c.setReadTimeout(90000);
        c.setRequestProperty("Authorization","Bearer "+config.key);
        c.setRequestProperty("Accept","application/json");
        return c;
    }
    static void verify(AppConfig config) throws Exception {
        if(config.accountMode){json(config,"GET","/v2/me",null);return;}
        HttpURLConnection c=connection(config,"/v1/models");
        try {
            error(c.getResponseCode());
            JSONObject body=new JSONObject(read(c.getInputStream()));
            if(!body.has("data"))throw new IOException("電腦回應格式不正確。");
        } finally { c.disconnect(); }
    }
    static Result upload(AppConfig config,File audio) throws Exception {
        HttpURLConnection c=connection(config,config.accountMode?"/v2/dictations":"/v1/audio/transcriptions");
        try {
            String boundary="LocalVoice"+UUID.randomUUID().toString().replace("-","");
            StringBuilder body=new StringBuilder();
            if(config.accountMode)c.setRequestProperty("Idempotency-Key",UUID.randomUUID().toString());
            else {
            part(body,boundary,"model","local-dictation");
            part(body,boundary,"language","zh");
            part(body,boundary,"response_format","json");
            part(body,boundary,"personal_prompt",config.personalPrompt);
            part(body,boundary,"vocabulary",config.vocabulary);
            part(body,boundary,"taiwan_places",String.valueOf(config.taiwanPlaces));
            }
            body.append("--").append(boundary).append("\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voice.m4a\"\r\nContent-Type: audio/mp4\r\n\r\n");
            byte[] head=body.toString().getBytes(StandardCharsets.UTF_8);
            byte[] tail=("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8);
            c.setRequestMethod("POST");c.setDoOutput(true);
            c.setRequestProperty("Content-Type","multipart/form-data; boundary="+boundary);
            c.setFixedLengthStreamingMode((long)head.length+audio.length()+tail.length);
            try(OutputStream out=c.getOutputStream();InputStream in=new FileInputStream(audio)) {
                out.write(head);byte[] bytes=new byte[16384];int count;
                while((count=in.read(bytes))!=-1)out.write(bytes,0,count);
                out.write(tail);
            }
            error(c.getResponseCode());
            JSONObject result=new JSONObject(read(c.getInputStream()));
            if(config.accountMode) {
                String id=result.getString("id");long deadline=System.nanoTime()+180000000000L;
                while(!"done".equals(result.optString("state"))) {
                    String state=result.optString("state");
                    if("failed".equals(state)||"expired".equals(state))throw new IOException(result.optString("message","處理未完成。"));
                    if(System.nanoTime()>deadline)throw new IOException("等待超過三分鐘。工作可能仍在處理，請稍後再試；不要連續重送。");
                    Thread.sleep(1000);
                    result=json(config,"GET","/v2/dictations/"+id,null);
                }
            }
            String warning=result.isNull("warning")?"":result.optString("warning","");
            JSONObject timings=result.optJSONObject("timings");
            return new Result(result.getString("text"),warning,timings==null?0:timings.optDouble("total_seconds",0));
        } finally {c.disconnect();}
    }
    static JSONObject json(AppConfig config,String method,String path,JSONObject body) throws Exception {
        HttpURLConnection c=connection(config,path);
        try {
            c.setRequestMethod(method);
            if(body!=null) {
                byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);
                c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(bytes.length);
                try(OutputStream out=c.getOutputStream()){out.write(bytes);}
            }
            error(c.getResponseCode());return new JSONObject(read(c.getInputStream()));
        } finally {c.disconnect();}
    }
    private static void part(StringBuilder b,String boundary,String name,String value) {
        b.append("--").append(boundary).append("\r\nContent-Disposition: form-data; name=\"").append(name)
            .append("\"\r\n\r\n").append(value).append("\r\n");
    }
    private static String read(InputStream source) throws Exception {
        try(InputStream in=source;ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] bytes=new byte[4096];int count;
            while((count=in.read(bytes))!=-1){out.write(bytes,0,count);if(out.size()>1024*1024)throw new IOException("回應太長。");}
            return out.toString("UTF-8");
        }
    }
    private static void error(int code) throws IOException {
        if(code>=200&&code<300)return;
        if(code==400)throw new IOException("資料格式不正確，請檢查輸入內容。");
        if(code==401)throw new IOException("帳號或密碼不正確、登入已失效，或私人金鑰不正確。請重新登入或配對。");
        if(code==402)throw new IOException("本月試用額度已用完，請聯絡管理者。");
        if(code==403)throw new IOException("密碼不正確或帳號已停用。");
        if(code==404)throw new IOException("找不到資料，請確認服務已更新。");
        if(code==409)throw new IOException("請求衝突，請重新整理後再試。");
        if(code==429)throw new IOException("上一段還在處理，請稍後再說一次。");
        if(code==413)throw new IOException("錄音太長，請分成較短的段落。");
        if(code==502||code==503||code==530)throw new IOException("電腦暫時連不到，請確認電腦未睡眠、服務已啟動。");
        throw new IOException("連線失敗（"+code+"），請檢查電腦網址。");
    }
    static String friendly(Exception e) {
        if(e instanceof SocketTimeoutException)return "等待逾時，請確認電腦與網路，再試較短的錄音。";
        if(e instanceof UnknownHostException||e instanceof ConnectException)return "找不到電腦，請確認網路；臨時網址變更後需要重新配對。";
        return e.getMessage()==null?"處理失敗，請重試。":e.getMessage();
    }
}
