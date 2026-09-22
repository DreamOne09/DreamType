package tw.localvoice.keyboard;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.json.JSONObject;

final class VoiceApi {
    interface Progress {void update(String message);}
    static final Progress QUIET=message->{};
    static final class ApiError extends IOException {
        final int code;
        ApiError(int code,String message){super(message);this.code=code;}
    }
    static final class Result {
        final String text,warning,id,mode,targetLanguage;
        final double computerSeconds;
        Result(String t,String w,double s,String id,String mode,String target){text=t;warning=w;computerSeconds=s;this.id=id;this.mode=mode;targetLanguage=target;}
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
            error(c);
            JSONObject body=new JSONObject(read(c.getInputStream()));
            if(!body.has("data"))throw new IOException("電腦回應格式不正確。");
        } finally { c.disconnect(); }
    }
    static Result upload(AppConfig config,File audio) throws Exception {
        return upload(config,audio,QUIET);
    }
    static Result upload(AppConfig config,File audio,Progress progress) throws Exception {
        if(audio.length()>EncryptedRecording.MAX_BYTES)throw new IOException("錄音檔太大，請分成較短段落。");
        return upload(config,java.nio.file.Files.readAllBytes(audio.toPath()),UUID.randomUUID().toString(),progress,false);
    }
    static Result upload(AppConfig config,byte[] audio,String requestId,Progress progress,boolean retryFailed) throws Exception {
        progress.update("正在上傳錄音…");
        HttpURLConnection c=connection(config,config.accountMode?"/v2/dictations":"/v1/audio/transcriptions");
        try {
            if(config.accountMode&&retryFailed)c.setRequestProperty("X-DreamType-Retry","1");
            String boundary="LocalVoice"+UUID.randomUUID().toString().replace("-","");
            StringBuilder body=new StringBuilder();
            if(config.accountMode){c.setRequestProperty("Idempotency-Key",requestId);c.setRequestProperty("X-DreamType-Receipt","1");c.setRequestProperty("X-DreamType-Mode",config.mode);c.setRequestProperty("X-DreamType-Target",config.targetLanguage);c.setRequestProperty("X-DreamType-Source",config.sourceLanguage);}
            else {
            part(body,boundary,"model","local-dictation");
            part(body,boundary,"language","zh");
            part(body,boundary,"mode",config.mode);part(body,boundary,"target_language",config.targetLanguage);part(body,boundary,"source_language",config.sourceLanguage);
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
            c.setFixedLengthStreamingMode((long)head.length+audio.length+tail.length);
            try(OutputStream out=c.getOutputStream()) {
                out.write(head);out.write(audio);out.write(tail);
            }
            error(c);
            JSONObject result=new JSONObject(read(c.getInputStream()));
            if(!config.accountMode&&config.mode.equals("translate"))requireTranslation(config,result);
            return config.accountMode?awaitResult(config,result,progress,config.mode.equals("translate")):result(result);
        } finally {c.disconnect();}
    }
    static Result recover(AppConfig config,Progress progress) throws Exception {
        if(!config.accountMode)throw new IOException("取回結果需要使用帳號登入。");
        progress.update("正在尋找上一筆錄音…");
        return awaitResult(config,json(config,"GET","/v2/me/latest-dictation",null),progress,false);
    }
    static boolean retryable(IOException error) {
        return !(error instanceof ApiError)||((ApiError)error).code>=500;
    }
    private static void requireTranslation(AppConfig config,JSONObject body)throws IOException {
        if(!"translate".equals(body.optString("mode"))||!config.targetLanguage.equals(body.optString("target_language")))throw new IOException("電腦未回傳指定的翻譯，請確認主機已更新至 0.8.0。未自動插入原文。");
    }
    private static Result awaitResult(AppConfig config,JSONObject body,Progress progress,boolean requireTranslation) throws Exception {
        long deadline=System.nanoTime()+180000000000L;int failures=0;
        while(true) {
            String state=body.optString("state");
            if("done".equals(state)){
                if(requireTranslation)requireTranslation(config,body);
                Result received=result(body);
                if(body.optBoolean("receipt_required",false))confirmReceipt(config,body.getString("id"),progress);
                return received;
            }
            if("failed".equals(state)||"expired".equals(state)||"none".equals(state))throw new IOException(body.optString("message","無法取回結果。"));
            if(!"queued".equals(state)&&!"running".equals(state))throw new IOException("服務回應格式不正確。");
            if(System.nanoTime()>deadline)throw new IOException("等候已超過三分鐘，可稍後從「更多 → 取回上一筆」查看。");
            progress.update("queued".equals(state)?"正在排隊，服務有 "+body.optInt("queue_size",0)+" 段等待中…":(config.mode.equals("translate")?"正在辨識與翻譯…":"正在辨識與整理…"));
            Thread.sleep(1000);
            try {body=json(config,"GET","/v2/dictations/"+body.getString("id"),null);failures=0;}
            catch(IOException e){
                if(!retryable(e)||++failures>3)throw e;
                progress.update("網路暫時中斷，正在重新連接…");Thread.sleep(failures*1000L);
            }
        }
    }
    private static void confirmReceipt(AppConfig config,String id,Progress progress)throws Exception {
        // The server's receipt is idempotent. Retry only this confirmation,
        // never the audio upload, when the confirmation response is lost.
        for(int attempt=0;;attempt++){
            try{json(config,"POST","/v2/dictations/"+id+"/receipt",new JSONObject());return;}
            catch(IOException error){
                if(!retryable(error)||attempt>=2)throw error;
                progress.update("文字已完成，正在確認接收…");Thread.sleep((attempt+1)*1000L);
            }
        }
    }
    private static Result result(JSONObject body) throws Exception {
        Object raw=body.opt("text");
        if(!(raw instanceof String))throw new IOException("沒有收到有效文字，請重試或取回上一筆。");
        String text=(String)raw;
        boolean visible=false;
        for(int i=0;i<text.length();){int cp=text.codePointAt(i);i+=Character.charCount(cp);if(!Character.isWhitespace(cp)&&!Character.isSpaceChar(cp)){visible=true;break;}}
        if(!visible)throw new IOException("沒有收到有效文字，請重試或取回上一筆。");
        String warning=body.isNull("warning")?"":body.optString("warning","");JSONObject timings=body.optJSONObject("timings");
        return new Result(text,warning,timings==null?0:timings.optDouble("total_seconds",0),body.optString("id",""),body.optString("mode","organize"),body.optString("target_language","zh-TW"));
    }
    static JSONObject json(AppConfig config,String method,String path,JSONObject body) throws Exception {
        HttpURLConnection c=connection(config,path);
        try {
            if(path.startsWith("/v2/")&&(method.equals("GET")||path.endsWith("/receipt")))c.setReadTimeout(15000);
            c.setRequestMethod(method);
            if(body!=null) {
                byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);
                c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(bytes.length);
                try(OutputStream out=c.getOutputStream()){out.write(bytes);}
            }
            error(c);return new JSONObject(read(c.getInputStream()));
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
    private static void error(HttpURLConnection connection) throws Exception {
        int code=connection.getResponseCode();
        if(code==409||code==429){
            String reason="";
            try {reason=new JSONObject(read(connection.getErrorStream())).optString("error_code","");}catch(Exception ignored){}
            // Show our own known messages, never arbitrary proxy/server response text.
            if(code==409&&reason.equals("result_unconfirmed"))throw new ApiError(code,"上一筆文字還沒取回，請到「更多 → 取回上一筆」確認，再繼續錄音。");
            if(code==429&&reason.equals("queue_full"))throw new ApiError(code,"目前使用的人較多，請稍後重試這段錄音；這次未扣額度。");
            if(code==429&&reason.equals("job_in_progress"))throw new ApiError(code,"上一段仍在處理，請稍後從「更多 → 取回上一筆」查看。");
            if(code==429&&reason.equals("auth_rate_limit"))throw new ApiError(code,"登入嘗試太頻繁，請一分鐘後再試。");
        }
        error(code);
    }
    private static void error(int code) throws IOException {
        if(code>=200&&code<300)return;
        if(code==400)throw new ApiError(code,"資料格式不正確，請檢查輸入內容。");
        if(code==401)throw new ApiError(code,"帳號或密碼不正確、登入已失效，或私人金鑰不正確。請重新登入或配對。");
        if(code==402)throw new ApiError(code,"本月試用額度已用完，請聯絡管理者。");
        if(code==403)throw new ApiError(code,"密碼不正確或帳號已停用。");
        if(code==404)throw new ApiError(code,"找不到資料，請確認服務已更新。");
        if(code==409)throw new ApiError(code,"請求衝突，請重新整理後再試。");
        if(code==429)throw new ApiError(code,"服務忙碌或請求太頻繁，請稍後重試。");
        if(code==413)throw new ApiError(code,"錄音太長，請分成較短的段落。");
        if(code==502||code==503||code==530)throw new ApiError(code,"電腦暫時連不到，請確認電腦未睡眠、服務已啟動。");
        throw new ApiError(code,"連線失敗（"+code+"），請檢查電腦網址。");
    }
    static String friendly(Exception e) {
        if(e instanceof SocketTimeoutException)return "等待逾時，請確認電腦與網路，再試較短的錄音。";
        if(e instanceof UnknownHostException||e instanceof ConnectException)return "找不到電腦，請確認網路；臨時網址變更後需要重新配對。";
        return e.getMessage()==null?"處理失敗，請重試。":e.getMessage();
    }
}
