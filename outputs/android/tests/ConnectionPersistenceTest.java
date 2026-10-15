package tw.localvoice.keyboard;
import android.content.*;
import java.lang.reflect.Proxy;
import java.nio.file.*;
import java.security.*;
import java.security.cert.Certificate;
import java.util.*;
import org.json.JSONObject;

/** Actual AppConfig save/replace with JCE AES and synthetic AndroidKeyStore/provider. */
public final class ConnectionPersistenceTest {
 public static final class SyntheticKeyStore extends KeyStoreSpi {
  private final javax.crypto.SecretKey key=new javax.crypto.spec.SecretKeySpec(new byte[16],"AES");
  public Key engineGetKey(String alias,char[] password){return key;}
  public boolean engineContainsAlias(String alias){return "localvoice.connection".equals(alias);}
  public void engineLoad(java.io.InputStream in,char[] password){}
  public void engineStore(java.io.OutputStream out,char[] password){throw new UnsupportedOperationException();}
  public Certificate[] engineGetCertificateChain(String alias){return null;}
  public Certificate engineGetCertificate(String alias){return null;}
  public Date engineGetCreationDate(String alias){return new Date(0);}
  public void engineSetKeyEntry(String a,Key k,char[] p,Certificate[] c){throw new UnsupportedOperationException();}
  public void engineSetKeyEntry(String a,byte[] k,Certificate[] c){throw new UnsupportedOperationException();}
  public void engineSetCertificateEntry(String a,Certificate c){throw new UnsupportedOperationException();}
  public void engineDeleteEntry(String a){throw new UnsupportedOperationException();}
  public Enumeration<String> engineAliases(){return Collections.enumeration(Collections.singleton("localvoice.connection"));}
  public int engineSize(){return 1;}
  public boolean engineIsKeyEntry(String a){return engineContainsAlias(a);}
  public boolean engineIsCertificateEntry(String a){return false;}
  public String engineGetCertificateAlias(Certificate c){return null;}
 }
 static final class Store {
  Map<String,Object> memory=new HashMap<>(),disk=new HashMap<>();int commits,failAt=-1;
  void seed(String k,Object v){memory.put(k,v);disk.put(k,v);}
  SharedPreferences prefs=(SharedPreferences)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.class},(p,m,a)->{
   if(m.getName().equals("edit"))return editor();
   if(m.getName().equals("contains"))return memory.containsKey(a[0]);
   if(m.getName().startsWith("get"))return memory.containsKey(a[0])?memory.get(a[0]):a[1];return null;
  });
  SharedPreferences.Editor editor(){Map<String,Object> changes=new HashMap<>();boolean[] clear={false};
   return (SharedPreferences.Editor)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{SharedPreferences.Editor.class},(p,m,a)->{
    if(m.getName().equals("clear")){clear[0]=true;return p;}
    if(m.getName().startsWith("put")){changes.put((String)a[0],a[1]);return p;}
    if(m.getName().equals("commit")){commits++;if(clear[0])memory.clear();memory.putAll(changes);if(commits==failAt)return false;disk.clear();disk.putAll(memory);return true;}
    return p;
   });
  }
 }
 static final class Ctx extends Context {
  Store connection=new Store(),style=new Store();java.io.File dir;
  Ctx(Path p){dir=p.toFile();connection.seed("server","https://old.invalid");style.seed("vocabulary","old synthetic word");}
  public SharedPreferences getSharedPreferences(String n,int m){return n.equals("connection")?connection.prefs:style.prefs;}
  public java.io.File getNoBackupFilesDir(){return dir;}
 }
 interface Operation {void run()throws Exception;}
 static boolean fails(Operation op)throws Exception{try{op.run();return false;}catch(java.io.IOException expected){return true;}}
 public static void main(String[] args)throws Exception {
  Path report=Paths.get(args[0]);if(Files.exists(report))throw new IllegalArgumentException("Evidence exists");
  if(Security.getProviders("KeyStore.AndroidKeyStore")!=null)throw new IllegalStateException("Do not shadow a real provider");
  Provider provider=new Provider("DreamTypeSyntheticKeyStore",1.0,"Disposable JVM contract provider"){};
  provider.put("KeyStore.AndroidKeyStore",SyntheticKeyStore.class.getName());Security.addProvider(provider);
  Path dir=Files.createTempDirectory("connection-persistence-");JSONObject checks=new JSONObject();
  AppConfig next=new AppConfig("https://new.invalid","synthetic-token-only",true,"","",true,true);
  JSONObject prefs=new JSONObject().put("vocabulary","new synthetic word");
  try{
   {Ctx c=new Ctx(dir);next.save(c);checks.put("save_encrypts_and_loads",AppConfig.load(c).sameSession(next)&&c.connection.disk.containsKey("cipher")&&!c.connection.disk.toString().contains(next.key));}
   {Ctx c=new Ctx(dir);c.connection.failAt=1;checks.put("direct_save_failure_reported",fails(()->next.save(c)));checks.put("failure_can_change_memory_but_not_disk",AppConfig.load(c).sameSession(next)&&!c.connection.disk.containsKey("cipher"));}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);c.connection.seed("server","https://changed.invalid");checks.put("stale_save_connection_rejected",fails(()->AppConfig.saveConnection(c,expected,next))&&c.connection.commits==0);}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);c.connection.failAt=1;checks.put("private_connection_failure_propagates",fails(()->AppConfig.saveConnection(c,expected,next)));}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);c.connection.failAt=1;checks.put("replace_stops_after_failed_clear",fails(()->AppConfig.replaceSession(c,expected,next,prefs))&&c.connection.commits==1&&!c.connection.memory.containsKey("cipher"));}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);c.connection.failAt=2;checks.put("replace_stops_after_failed_save",fails(()->AppConfig.replaceSession(c,expected,next,prefs))&&c.style.commits==1&&!c.connection.disk.containsKey("cipher"));}
   {Ctx c=new Ctx(dir);c.connection.seed("account",true);AppConfig expected=AppConfig.load(c);c.connection.failAt=2;checks.put("account_connection_failure_propagates",fails(()->AppConfig.saveConnection(c,expected,next)));}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);c.style.failAt=2;checks.put("style_failure_after_login_reported",fails(()->AppConfig.replaceSession(c,expected,next,prefs))&&AppConfig.load(c).sameSession(next));}
   {Ctx c=new Ctx(dir);AppConfig expected=AppConfig.load(c);AppConfig.replaceSession(c,expected,next,prefs);c.connection.memory=new HashMap<>(c.connection.disk);c.style.memory=new HashMap<>(c.style.disk);checks.put("successful_replace_survives_simulated_reload",AppConfig.load(c).sameSession(next)&&"new synthetic word".equals(AppConfig.load(c).vocabulary));}
  }finally{Security.removeProvider(provider.getName());Files.deleteIfExists(dir.resolve("pending-recording.bin"));Files.deleteIfExists(dir.resolve("pending-recording.bin.tmp"));Files.delete(dir);}
  boolean passed=true;for(String n:checks.keySet())passed &= checks.getBoolean(n);
  JSONObject result=new JSONObject().put("scope","Actual AppConfig.save/saveConnection/replaceSession, real JCE AES-GCM; synthetic KeyStore, Base64 bridge, Context and memory/disk stores. Not Android Keystore/disk/UI.").put("checks",checks).put("passed",passed).put("synthetic_provider_removed",Security.getProvider(provider.getName())==null).put("temporary_directory_removed",!Files.exists(dir));
  Files.write(report,result.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
  System.out.println("Connection persistence: passed="+passed+"; evidence saved");if(!passed)throw new AssertionError("See persistence evidence");
 }
}
