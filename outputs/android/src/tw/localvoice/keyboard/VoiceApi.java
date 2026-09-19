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
        HttpURLConnection c=connection(config,"/v1/models");
        try {
            error(c.getResponseCode());
            JSONObject body=new JSONObject(read(c.getInputStream()));
            if(!body.has("data"))throw new IOException("電腦回應格式不正確。");
        } finally { c.disconnect(); }
    }
    static Result upload(AppConfig config,File audio) throws Exception {
        HttpURLConnection c=connection(config,"/v1/audio/transcriptions");
        try {
            String boundary="LocalVoice"+UUID.randomUUID().toString().replace("-","");
            StringBuilder body=new StringBuilder();
            part(body,boundary,"model","local-dictation");
            part(body,boundary,"language","zh");
            part(body,boundary,"response_format","json");
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
            String warning=result.isNull("warning")?"":result.optString("warning","");
            JSONObject timings=result.optJSONObject("timings");
            return new Result(result.getString("text"),warning,timings==null?0:timings.optDouble("total_seconds",0));
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
        if(code==200)return;
        if(code==401)throw new IOException("金鑰不正確，請從電腦試用頁重新配對。");
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
