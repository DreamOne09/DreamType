package tw.localvoice.keyboard;

import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.inputmethodservice.InputMethodService;
import android.media.MediaRecorder;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.view.inputmethod.*;
import android.widget.*;
import java.io.File;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class VoiceIme extends InputMethodService {
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private MediaRecorder recorder;
    private File recording;
    private long began,generation;
    private boolean recordingNow=false,busy=false,pending=false,protectedField=false;
    private volatile boolean destroyed=false;
    private String lastText="";
    private TextView status,preview;
    private Button mic,insert;
    private final Runnable tick=new Runnable(){public void run(){if(!recordingNow)return;long seconds=(SystemClock.elapsedRealtime()-began)/1000;status.setText("正在錄音　"+seconds+" 秒");if(seconds>=120){finishRecording();return;}main.postDelayed(this,500);}};
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void setup(){Intent i=new Intent(this,SetupActivity.class);i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);}
    private Button button(LinearLayout parent,String label,View.OnClickListener action,float weight) {
        Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(15);b.setMinWidth(0);b.setPadding(dp(3),0,dp(3),0);b.setOnClickListener(action);
        Ui.button(b,false);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(48),weight);lp.setMargins(dp(2),dp(8),dp(2),0);parent.addView(b,lp);return b;
    }
    @Override public boolean onEvaluateFullscreenMode(){return false;}
    @Override public View onCreateInputView() {
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(12),dp(12),dp(12),dp(12));root.setBackgroundColor(Ui.PAPER);
        status=new TextView(this);status.setTextSize(14);status.setTextColor(Ui.INK);status.setPadding(dp(5),dp(3),dp(5),dp(6));status.setMaxLines(3);root.addView(status);
        ScrollView scroll=new ScrollView(this);preview=new TextView(this);preview.setTextSize(17);preview.setTextColor(Ui.INK);preview.setPadding(dp(8),dp(4),dp(8),dp(4));scroll.addView(preview);root.addView(scroll,new LinearLayout.LayoutParams(-1,dp(66)));
        mic=new Button(this);mic.setAllCaps(false);mic.setTextSize(20);mic.setTextColor(Color.WHITE);Ui.button(mic,true);mic.setOnClickListener(v->{if(recordingNow)finishRecording();else startRecording();});root.addView(mic,new LinearLayout.LayoutParams(-1,dp(64)));
        LinearLayout row=new LinearLayout(this);root.addView(row);
        button(row,"換鍵盤",v->((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker(),1.15f);
        button(row,"刪除",v->{InputConnection c=getCurrentInputConnection();if(c!=null)c.deleteSurroundingTextInCodePoints(1,0);},.85f);
        button(row,"換行",v->{InputConnection c=getCurrentInputConnection();if(c!=null)c.commitText("\n",1);},.85f);
        insert=button(row,"插入",v->insertPending(),.85f);
        button(row,"設定",v->setup(),.85f);
        preview.setText(lastText);refresh();return root;
    }
    @Override public void onStartInput(EditorInfo info,boolean restarting){super.onStartInput(info,restarting);generation++;cancelRecording();
        int cls=info.inputType&InputType.TYPE_MASK_CLASS,var=info.inputType&InputType.TYPE_MASK_VARIATION;
        protectedField=(cls==InputType.TYPE_CLASS_TEXT&&(var==InputType.TYPE_TEXT_VARIATION_PASSWORD||var==InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD||var==InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD))||(cls==InputType.TYPE_CLASS_NUMBER&&var==InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        refresh();
    }
    @Override public void onStartInputView(EditorInfo info,boolean restarting){super.onStartInputView(info,restarting);refresh();}
    @Override public void onFinishInputView(boolean finishingInput){generation++;cancelRecording();super.onFinishInputView(finishingInput);}
    @Override public void onFinishInput(){generation++;cancelRecording();super.onFinishInput();}
    private void refresh() {
        if(mic==null)return;
        mic.setText(recordingNow?"停止並整理":busy?"電腦整理中…":"開始說話");mic.setEnabled(!busy&&!protectedField);insert.setEnabled(pending&&!protectedField&&!busy);
        if(recordingNow)return;
        if(protectedField)status.setText("密碼欄位不使用語音，請切回原本鍵盤。");
        else if(busy)status.setText("正在傳給電腦整理…");
        else if(!AppConfig.load(this).ready())status.setText("請先按「設定」，連接你的電腦。");
        else if(pending)status.setText("文字已整理好，按「插入」。");
        else status.setText("DreamType · 自然說，清楚寫。");
    }
    private void startRecording() {
        if(busy||protectedField)return;
        AppConfig config=AppConfig.load(this);
        if(!config.ready()||checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){setup();return;}
        try {
            recording=File.createTempFile("voice-",".m4a",getCacheDir());
            recorder=Build.VERSION.SDK_INT>=31?new MediaRecorder(this):new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);recorder.setAudioSamplingRate(16000);recorder.setAudioEncodingBitRate(64000);
            recorder.setOutputFile(recording.getAbsolutePath());recorder.prepare();recorder.start();
            began=SystemClock.elapsedRealtime();recordingNow=true;pending=false;lastText="";preview.setText("");refresh();main.post(tick);
        } catch(Exception e){cancelRecording();refresh();status.setText("無法錄音，請確認麥克風權限或其他 App 是否正在使用麥克風。");}
    }
    private void finishRecording() {
        if(!recordingNow)return;
        recordingNow=false;main.removeCallbacks(tick);
        File audio=recording;recording=null;
        try{recorder.stop();}catch(RuntimeException e){recorder.release();recorder=null;if(audio!=null)audio.delete();refresh();status.setText("錄音太短，請再說一次。");return;}
        recorder.release();recorder=null;
        if(audio==null){refresh();return;}
        final long expected=generation,start=SystemClock.elapsedRealtime();final AppConfig config=AppConfig.load(this);
        busy=true;refresh();
        worker.execute(()->{
            VoiceApi.Result result=null;String error=null;
            try{result=VoiceApi.upload(config,audio);}catch(Exception e){error=VoiceApi.friendly(e);}finally{audio.delete();}
            final VoiceApi.Result done=result;final String problem=error;
            main.post(()->{
                if(destroyed)return;busy=false;
                if(problem!=null){refresh();status.setText(problem+" 請重新錄音。");return;}
                lastText=done.text;pending=!lastText.trim().isEmpty();preview.setText(lastText);refresh();
                boolean inserted=false;
                if(pending&&config.autoInsert&&generation==expected&&isInputViewShown()&&!protectedField)inserted=insertPending();
                String timing=String.format(Locale.TAIWAN,"%.1f 秒",(SystemClock.elapsedRealtime()-start)/1000.0);
                if(!done.warning.isEmpty())status.setText("排版暫時失敗，已保留辨識原文。"+(inserted?"已輸入。":"按插入可使用。"));
                else status.setText(lastText.trim().isEmpty()?"沒有辨識到語音，請再試一次。":(inserted?"已輸入　":"已整理，按插入　")+timing);
            });
        });
    }
    private boolean insertPending(){
        if(!pending||protectedField)return false;InputConnection c=getCurrentInputConnection();if(c==null)return false;
        if(c.commitText(lastText,1)){pending=false;insert.setEnabled(false);return true;}return false;
    }
    private void cancelRecording(){main.removeCallbacks(tick);recordingNow=false;if(recorder!=null){try{recorder.stop();}catch(Exception ignored){}recorder.release();recorder=null;}if(recording!=null){recording.delete();recording=null;}}
    @Override public void onDestroy(){destroyed=true;cancelRecording();worker.shutdownNow();main.removeCallbacksAndMessages(null);super.onDestroy();}
}
