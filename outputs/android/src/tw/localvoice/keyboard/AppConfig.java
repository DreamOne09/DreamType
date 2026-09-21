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
    final String server, key, personalPrompt, vocabulary;
    final boolean autoInsert, taiwanPlaces, accountMode;
    AppConfig(String server, String key, boolean autoInsert) {
        this(server,key,autoInsert,"","",true);
    }
    AppConfig(String server, String key, boolean autoInsert,String personalPrompt,String vocabulary,boolean taiwanPlaces) {
        this(server,key,autoInsert,personalPrompt,vocabulary,taiwanPlaces,false);
    }
    AppConfig(String server, String key, boolean autoInsert,String personalPrompt,String vocabulary,boolean taiwanPlaces,boolean accountMode) {
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
        return new AppConfig(p.getString("server",""),key,p.getBoolean("auto",false),style.getString("prompt",""),style.getString("vocabulary",""),style.getBoolean("taiwan",true),p.getBoolean("account",false));
    }
    void save(Context c) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,secret());
        String encrypted=Base64.encodeToString(cipher.doFinal(key.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);
        c.getSharedPreferences("connection",Context.MODE_PRIVATE).edit().putString("server",server)
            .putString("cipher",encrypted).putString("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP))
            .putBoolean("auto",autoInsert).putBoolean("account",accountMode).commit();
    }
    static void saveStyle(Context c,org.json.JSONObject prefs) {
        c.getSharedPreferences("style",Context.MODE_PRIVATE).edit().putString("prompt",prefs.optString("personal_prompt",""))
            .putString("vocabulary",prefs.optString("vocabulary","" )).putBoolean("taiwan",prefs.optBoolean("taiwan_places",true)).commit();
    }
    static void clearSession(Context c) {
        String server=load(c).server;
        c.getSharedPreferences("connection",Context.MODE_PRIVATE).edit().clear().putString("server",server).commit();
        c.getSharedPreferences("style",Context.MODE_PRIVATE).edit().clear().commit();
        Draft.clear();
        PendingAudio.clear(c);
    }
}
