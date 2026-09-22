package tw.localvoice.keyboard;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.net.URI;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class AppConfig {
    final String server, key, personalPrompt, vocabulary, mode, targetLanguage, sourceLanguage;
    static final String[] LANGUAGE_CODES={"zh-TW","en","ja","th","ms","ko","vi","id"};
    static final String[] LANGUAGE_NAMES={"台灣繁中","英文","日文","泰文","馬來文","韓文","越南文","印尼文"};
    static int languageIndex(String code){for(int i=0;i<LANGUAGE_CODES.length;i++)if(LANGUAGE_CODES[i].equals(code))return i;return 0;}
    String modeLabel(){return mode.equals("translate")?"翻譯 → "+LANGUAGE_NAMES[languageIndex(targetLanguage)]:"整理 · 台灣繁中";}
    final boolean autoInsert, taiwanPlaces, accountMode;
    AppConfig(String server, String key, boolean autoInsert) {
        this(server,key,autoInsert,"","",true);
    }
    AppConfig(String server, String key, boolean autoInsert,String personalPrompt,String vocabulary,boolean taiwanPlaces) {
        this(server,key,autoInsert,personalPrompt,vocabulary,taiwanPlaces,false);
    }
    AppConfig(String server, String key, boolean autoInsert,String personalPrompt,String vocabulary,boolean taiwanPlaces,boolean accountMode) {
        this(server,key,autoInsert,personalPrompt,vocabulary,taiwanPlaces,accountMode,"organize","en","zh-TW");
    }
    AppConfig(String server,String key,boolean autoInsert,String personalPrompt,String vocabulary,boolean taiwanPlaces,boolean accountMode,String mode,String targetLanguage,String sourceLanguage){
        this.mode=mode;this.targetLanguage=targetLanguage;this.sourceLanguage=sourceLanguage;
        this.server=server; this.key=key; this.autoInsert=autoInsert;
        this.personalPrompt=personalPrompt;this.vocabulary=vocabulary;this.taiwanPlaces=taiwanPlaces;
        this.accountMode=accountMode;
    }
    boolean ready() { return !server.isEmpty() && !key.isEmpty(); }
    static String normalize(String text) throws Exception {
        String s=text.trim();
        while(s.endsWith("/")) s=s.substring(0,s.length()-1);
        if(s.endsWith("/v1/audio/transcriptions")) s=s.substring(0,s.length()-"/v1/audio/transcriptions".length());
        URI u=new URI(s);
        if(!"https".equalsIgnoreCase(u.getScheme()) || u.getHost()==null || u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null || !(u.getPath()==null || u.getPath().isEmpty()))
            throw new Exception("請使用完整 HTTPS 電腦網址，不含額外路徑。");
        return s;
    }
    static synchronized SecretKey secret() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias="localvoice.connection";
        if(!store.containsAlias(alias)) {
            KeyGenerator g=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            g.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            g.generateKey();
        }
        return (SecretKey)store.getKey(alias,null);
    }
    static AppConfig load(Context c) {
        synchronized(PendingAudio.class) {
        SharedPreferences p=c.getSharedPreferences("connection",Context.MODE_PRIVATE);
        String key="";
        try {
            if(p.contains("cipher")) {
                Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE,secret(),new GCMParameterSpec(128,Base64.decode(p.getString("iv",""),Base64.NO_WRAP)));
                key=new String(cipher.doFinal(Base64.decode(p.getString("cipher",""),Base64.NO_WRAP)),java.nio.charset.StandardCharsets.UTF_8);
            }
        } catch(Exception ignored) { /* Re-pair if a restored/invalid key cannot be decrypted. */ }
        SharedPreferences style=c.getSharedPreferences("style",Context.MODE_PRIVATE);
        return new AppConfig(p.getString("server",""),key,p.getBoolean("auto",false),style.getString("prompt",""),style.getString("vocabulary",""),style.getBoolean("taiwan",true),p.getBoolean("account",false),style.getString("mode","organize"),style.getString("target_language","en"),style.getString("source_language","zh-TW"));
        }
    }
    void save(Context c) throws Exception {
        synchronized(PendingAudio.class) {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,secret());
        String encrypted=Base64.encodeToString(cipher.doFinal(key.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);
        c.getSharedPreferences("connection",Context.MODE_PRIVATE).edit().putString("server",server)
            .putString("cipher",encrypted).putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP))
            .putBoolean("auto",autoInsert).putBoolean("account",accountMode).commit();
        }
    }
    static void saveStyle(Context c,org.json.JSONObject prefs) {
        synchronized(PendingAudio.class) {
        c.getSharedPreferences("style",Context.MODE_PRIVATE).edit().putString("prompt",prefs.optString("personal_prompt",""))
            .putString("vocabulary",prefs.optString("vocabulary","" )).putBoolean("taiwan",prefs.optBoolean("taiwan_places",true)).putString("mode",prefs.optString("mode","organize")).putString("target_language",prefs.optString("target_language","en")).putString("source_language",prefs.optString("source_language","zh-TW")).commit();
        }
    }
    // Share the recording lock: prepare/read already take this lock before loading
    // credentials. Never acquire it while holding the separate Keystore lock.
    private static void requireSession(Context c,AppConfig expected)throws java.io.IOException {
        AppConfig current=load(c);
        if(!current.key.equals(expected.key)||!current.server.equals(expected.server)||current.accountMode!=expected.accountMode)
            throw new java.io.IOException("登入或連線已變更，請重新開啟頁面再操作。");
    }
    static void savePreferences(Context c,AppConfig expected,org.json.JSONObject prefs,Boolean auto)throws Exception {
        synchronized(PendingAudio.class){requireSession(c,expected);saveStyle(c,prefs);
            if(auto!=null)c.getSharedPreferences("connection",Context.MODE_PRIVATE).edit().putBoolean("auto",auto).commit();}
    }
    static void clearSessionIfCurrent(Context c,AppConfig expected)throws Exception {
        synchronized(PendingAudio.class){requireSession(c,expected);clearSession(c);}
    }
    static void replaceSession(Context c,AppConfig expected,AppConfig next,org.json.JSONObject prefs)throws Exception {
        synchronized(PendingAudio.class){requireSession(c,expected);clearSession(c);next.save(c);if(prefs!=null)saveStyle(c,prefs);}
    }
    static void saveConnection(Context c,AppConfig expected,AppConfig next)throws Exception {
        synchronized(PendingAudio.class){requireSession(c,expected);if(expected.accountMode)clearSession(c);next.save(c);}
    }
    static void clearSession(Context c) {
        synchronized(PendingAudio.class) {
        String server=load(c).server;
        c.getSharedPreferences("connection",Context.MODE_PRIVATE).edit().clear().putString("server",server).commit();
        c.getSharedPreferences("style",Context.MODE_PRIVATE).edit().clear().commit();
        Draft.clear();
        PendingAudio.clear(c);
        }
    }
}
