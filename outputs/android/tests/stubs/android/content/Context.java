package android.content;
public abstract class Context {
 public static final int MODE_PRIVATE=0;
 public abstract SharedPreferences getSharedPreferences(String name,int mode);
 public java.io.File getNoBackupFilesDir(){throw new UnsupportedOperationException("Not used by this contract");}
}