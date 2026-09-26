package tw.localvoice.keyboard;

import android.app.Application;
import java.io.File;

/** Drop abandoned MediaRecorder files before any component starts recording. */
public final class DreamTypeApplication extends Application {
    @Override public void onCreate() {
        super.onCreate();
        File[] files=getCacheDir().listFiles();
        if(files==null)return;
        for(File file:files){
            String name=file.getName();
            if(name.startsWith("voice-")&&name.endsWith(".m4a")&&file.isFile()&&!file.delete())
                android.util.Log.w("DreamType","Unable to remove abandoned recording cache");
        }
    }
}
