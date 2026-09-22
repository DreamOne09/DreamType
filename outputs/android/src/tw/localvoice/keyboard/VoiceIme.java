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
    private boolean retained=false;
    private volatile boolean destroyed=false;
    private String lastText="";
    private AppConfig sessionConfig,recordingConfig;
    private TextView status,preview;
    private Button mic,edit,discard,modeButton;
    private LinearLayout editRow;
    private ScrollView resultArea;
    private PopupWindow languagePanel;
    private final java.util.ArrayList<Button> languageChoices=new java.util.ArrayList<>();
    private int hoveredLanguage=-1;
    private boolean languageGesture=false,deleteHeld=false;
    private float touchX,touchY;
    private final Runnable holdLanguage=()->{if(canChooseLanguage()){languageGesture=true;showLanguages();mic.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);}};
    private final Runnable repeatDelete=new Runnable(){public void run(){if(deleteHeld){backspace();main.postDelayed(this,90);}}};
    private boolean canChooseLanguage(){return !busy&&!recordingNow&&!pending&&!retained&&!protectedField&&mic!=null&&mic.isEnabled();}
    private void backspace(){
        InputConnection c=getCurrentInputConnection();if(c==null)return;
        // Let the editor handle selections and composed characters like a hardware Backspace.
        c.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DEL));
        c.sendKeyEvent(new KeyEvent(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DEL));
    }
    private void closeLanguages(){if(languagePanel!=null){languagePanel.dismiss();languagePanel=null;}languageChoices.clear();hoveredLanguage=-1;}
    private void selectLanguage(int index,boolean record){
        if(!canChooseLanguage()){closeLanguages();return;}
        AppConfig config=AppConfig.load(this);
        getSharedPreferences("style",MODE_PRIVATE).edit().putString("mode",index==0?"organize":"translate")
            .putString("target_language",index==0?config.targetLanguage:AppConfig.LANGUAGE_CODES[index-1]).commit();
        closeLanguages();refresh();if(record)startRecording();
    }
    private void showLanguages(){
        if(!canChooseLanguage())return;closeLanguages();
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);panel.setPadding(dp(8),dp(8),dp(8),dp(8));panel.setBackgroundColor(Ui.PAPER);
        TextView title=new TextView(this);title.setText("往上滑選語言，放開開始說話");title.setTextColor(Ui.MUTED);title.setTextSize(14);title.setGravity(Gravity.CENTER);panel.addView(title,new LinearLayout.LayoutParams(-1,dp(32)));
        LinearLayout row=null;
        for(int i=0;i<=AppConfig.LANGUAGE_NAMES.length;i++){
            if(i%3==0){row=new LinearLayout(this);panel.addView(row);}
            final int choice=i;
            Button b=button(row,i==0?"原文整理":i==1?"繁中翻譯":AppConfig.LANGUAGE_NAMES[i-1],v->selectLanguage(choice,true),1);
            b.setContentDescription(i==0?"整理成台灣繁中":"翻譯成"+AppConfig.LANGUAGE_NAMES[i-1]);languageChoices.add(b);
        }
        int width=Math.min(getResources().getDisplayMetrics().widthPixels-dp(24),dp(360));
        int height=dp(48+56*((languageChoices.size()+2)/3));
        languagePanel=new PopupWindow(panel,width,height,false);languagePanel.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Ui.PAPER));languagePanel.setElevation(dp(12));languagePanel.setOutsideTouchable(true);
        languagePanel.showAsDropDown(mic,(mic.getWidth()-width)/2,-mic.getHeight()-height-dp(8));
    }
    private void trackLanguage(float x,float y){
        hoveredLanguage=-1;
        for(int i=0;i<languageChoices.size();i++){
            Button b=languageChoices.get(i);int[] pos=new int[2];b.getLocationOnScreen(pos);
            boolean hit=x>=pos[0]&&x<pos[0]+b.getWidth()&&y>=pos[1]&&y<pos[1]+b.getHeight();
            Ui.button(b,hit);if(hit)hoveredLanguage=i;
        }
    }
    private boolean micTouch(View view,android.view.MotionEvent event){
        switch(event.getActionMasked()){
            case MotionEvent.ACTION_DOWN:
                touchX=event.getRawX();touchY=event.getRawY();languageGesture=false;view.setPressed(true);
                if(canChooseLanguage())main.postDelayed(holdLanguage,ViewConfiguration.getLongPressTimeout());return true;
            case MotionEvent.ACTION_MOVE:
                if(languageGesture)trackLanguage(event.getRawX(),event.getRawY());
                else if(Math.abs(event.getRawX()-touchX)>dp(24)||Math.abs(event.getRawY()-touchY)>dp(24)){main.removeCallbacks(holdLanguage);view.setPressed(false);}return true;
            case MotionEvent.ACTION_UP:
                main.removeCallbacks(holdLanguage);boolean click=view.isPressed();view.setPressed(false);
                if(languageGesture){int selected=hoveredLanguage;languageGesture=false;if(selected>=0)selectLanguage(selected,true);}
                else if(click)view.performClick();return true;
            case MotionEvent.ACTION_CANCEL:
                main.removeCallbacks(holdLanguage);view.setPressed(false);languageGesture=false;closeLanguages();return true;
            default:return true;
        }
    }
    private final Runnable tick=new Runnable(){public void run(){if(!recordingNow)return;long seconds=(SystemClock.elapsedRealtime()-began)/1000;status.setText("正在錄音　"+seconds+" 秒");if(seconds>=118){finishRecording();return;}main.postDelayed(this,500);}};
    private int dp(int value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private void setup(){Intent i=new Intent(this,HomeActivity.class);i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);}
    private Button button(LinearLayout parent,String label,View.OnClickListener action,float weight) {
        Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextSize(15);b.setMinWidth(0);b.setPadding(dp(3),0,dp(3),0);b.setOnClickListener(action);
        Ui.button(b,false);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(48),weight);lp.setMargins(dp(2),dp(8),dp(2),0);parent.addView(b,lp);return b;
    }
    @Override public boolean onEvaluateFullscreenMode(){return false;}
    @Override public View onCreateInputView() {
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(12),dp(12),dp(12),dp(12));root.setBackgroundColor(Ui.PAPER);
        LinearLayout modes=new LinearLayout(this);root.addView(modes);
        modeButton=button(modes,"整理 · 台灣繁中 ▾",v->chooseMode(v),1f);
        status=new TextView(this);status.setTextSize(14);status.setTextColor(Ui.INK);status.setPadding(dp(5),dp(3),dp(5),dp(6));status.setMaxLines(3);status.setGravity(Gravity.CENTER);root.addView(status);
        ScrollView scroll=new ScrollView(this);resultArea=scroll;preview=new TextView(this);preview.setTextSize(17);preview.setTextColor(Ui.INK);preview.setPadding(dp(8),dp(4),dp(8),dp(4));scroll.addView(preview);root.addView(scroll,new LinearLayout.LayoutParams(-1,dp(66)));
        LinearLayout controls=new LinearLayout(this);controls.setGravity(Gravity.CENTER_VERTICAL);root.addView(controls);
        Button switcher=button(controls,"換鍵盤",v->((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker(),1f);
        mic=new Button(this);mic.setAllCaps(false);mic.setTextSize(22);mic.setTextColor(Color.WHITE);Ui.button(mic,true);
        android.graphics.drawable.GradientDrawable circle=new android.graphics.drawable.GradientDrawable();circle.setShape(android.graphics.drawable.GradientDrawable.OVAL);circle.setColor(Ui.INK);
        mic.setBackground(new android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x55777777),circle,null));
        mic.setOnClickListener(v->{closeLanguages();if(pending)insertPending();else if(recordingNow)finishRecording();else if(retained)retryRecording();else startRecording();});
        mic.setOnTouchListener(this::micTouch);mic.setOnLongClickListener(v->{if(!canChooseLanguage())return false;showLanguages();return true;});
        LinearLayout.LayoutParams circleLayout=new LinearLayout.LayoutParams(dp(112),dp(112));circleLayout.setMargins(dp(16),dp(8),dp(16),dp(8));controls.addView(mic,circleLayout);
        Button delete=button(controls,"⌫",v->backspace(),1f);delete.setTextSize(26);delete.setContentDescription("退格刪除");
        delete.setOnTouchListener((v,e)->{switch(e.getActionMasked()){
            case MotionEvent.ACTION_DOWN:deleteHeld=true;v.setPressed(true);backspace();main.postDelayed(repeatDelete,400);return true;
            case MotionEvent.ACTION_MOVE:if(e.getX()<0||e.getY()<0||e.getX()>v.getWidth()||e.getY()>v.getHeight()){deleteHeld=false;main.removeCallbacks(repeatDelete);v.setPressed(false);}return true;
            case MotionEvent.ACTION_UP:case MotionEvent.ACTION_CANCEL:deleteHeld=false;main.removeCallbacks(repeatDelete);v.setPressed(false);return true;
            default:return true;}});
        TextView hint=new TextView(this);hint.setText("點一下說話 · 長按往上滑翻譯");hint.setTextSize(13);hint.setTextColor(Ui.MUTED);hint.setGravity(Gravity.CENTER);root.addView(hint);
        LinearLayout row=new LinearLayout(this);root.addView(row);
        button(row,"換行",v->{InputConnection c=getCurrentInputConnection();if(c!=null)c.commitText("\n",1);},1f);
        button(row,"更多",v->{PopupMenu menu=new PopupMenu(this,v);String[] items={"刪除一字","換行","取回上一筆","刪除保留錄音","我的設定","連線設定"};for(String item:items)menu.getMenu().add(item);menu.setOnMenuItemClickListener(item->{String name=item.getTitle().toString();InputConnection c=getCurrentInputConnection();if(name.equals("刪除一字")){if(c!=null)c.deleteSurroundingTextInCodePoints(1,0);}else if(name.equals("換行")){if(c!=null)c.commitText("\n",1);}else if(name.equals("取回上一筆")){recoverLast();}else if(name.equals("刪除保留錄音")){if(!busy&&!recordingNow){PendingAudio.clear(this);refresh();}}else if(name.equals("我的設定")){Intent i=new Intent(this,ManageActivity.class);i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);}else setup();return true;});menu.show();},1f);
        editRow=new LinearLayout(this);root.addView(editRow);
        edit=button(editRow,"修改文字",v->{if(!pending||busy||protectedField)return;Draft.begin(lastText);Intent i=new Intent(this,EditActivity.class);i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);startActivity(i);},2f);
        discard=button(editRow,"捨棄",v->{pending=false;lastText="";Draft.clear();preview.setText("");refresh();},1f);
        preview.setText(lastText);refresh();return root;
    }
    @Override public void onStartInput(EditorInfo info,boolean restarting){super.onStartInput(info,restarting);generation++;cancelRecording();
        int cls=info.inputType&InputType.TYPE_MASK_CLASS,var=info.inputType&InputType.TYPE_MASK_VARIATION;
        protectedField=(cls==InputType.TYPE_CLASS_TEXT&&(var==InputType.TYPE_TEXT_VARIATION_PASSWORD||var==InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD||var==InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD))||(cls==InputType.TYPE_CLASS_NUMBER&&var==InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        refresh();
    }
    @Override public void onStartInputView(EditorInfo info,boolean restarting){super.onStartInputView(info,restarting);if(!getPackageName().equals(info.packageName)&&Draft.edited){lastText=Draft.text==null?"":Draft.text;pending=!lastText.trim().isEmpty();if(preview!=null)preview.setText(lastText);Draft.clear();}refresh();}
    @Override public void onFinishInputView(boolean finishingInput){generation++;cancelRecording();super.onFinishInputView(finishingInput);}
    @Override public void onFinishInput(){generation++;cancelRecording();super.onFinishInput();}
    private void refresh() {
        if(mic==null)return;
        AppConfig active=AppConfig.load(this);
        if(!active.sameSession(sessionConfig)){sessionConfig=active;pending=false;lastText="";Draft.clear();preview.setText("");}
        retained=PendingAudio.exists(this,AppConfig.load(this));
        AppConfig chosen=recordingNow&&recordingConfig!=null?recordingConfig:active;boolean translating=chosen.mode.equals("translate");
        modeButton.setText(chosen.modeLabel()+" ▾");modeButton.setEnabled(!busy&&!recordingNow&&!pending&&!retained);
        mic.setContentDescription(recordingNow?(translating?"停止並翻譯":"停止並整理"):busy?(translating?"正在翻譯…":"正在整理…"):pending?"插入文字":retained?"重試上一段":"開始說話");mic.setText(recordingNow?"停止":busy?"處理中":pending?"插入":retained?"重試":"說話");mic.setEnabled(!busy&&!protectedField);
        if(editRow!=null)editRow.setVisibility(pending?View.VISIBLE:View.GONE);
        if(resultArea!=null)resultArea.setVisibility(pending?View.VISIBLE:View.GONE);
        if(discard!=null)discard.setEnabled(pending&&!busy&&!recordingNow);
        if(edit!=null)edit.setEnabled(pending&&!protectedField&&!busy&&!recordingNow);
        if(getCurrentInputEditorInfo()!=null&&getPackageName().equals(getCurrentInputEditorInfo().packageName)){mic.setEnabled(false);if(edit!=null)edit.setEnabled(false);status.setText("請切換 Gboard 修改；完成後回到原 App 插入。");return;}
        if(recordingNow)return;
        if(protectedField)status.setText("密碼欄位不使用語音，請切回原本鍵盤。");
        else if(busy)status.setText("已送出，正在排隊或處理…");
        else if(!AppConfig.load(this).ready())status.setText("請從「更多」開啟連線設定。");
        else if(pending)status.setText("文字已準備好，可修改或插入。");
        else if(retained)status.setText("有未完成錄音，可重試；不想保留可從「更多」刪除。");
        else status.setText(translating?(chosen.sourceLanguage.equals("zh-TW")?"說中文，翻成":"說話，翻成")+AppConfig.LANGUAGE_NAMES[AppConfig.languageIndex(chosen.targetLanguage)]+"。":"DreamType · 自然說，清楚寫。");
    }
    private void chooseMode(View anchor){
        if(busy||recordingNow||pending||retained)return;
        PopupMenu menu=new PopupMenu(this,anchor);menu.getMenu().add(0,0,0,"整理成台灣繁中");
        for(int i=0;i<AppConfig.LANGUAGE_NAMES.length;i++)menu.getMenu().add(0,i+1,i+1,"翻譯成"+AppConfig.LANGUAGE_NAMES[i]);
        menu.setOnMenuItemClickListener(item->{
            AppConfig config=AppConfig.load(this);int index=item.getItemId();
            String mode=index==0?"organize":"translate",target=index==0?config.targetLanguage:AppConfig.LANGUAGE_CODES[index-1];
            // Local selection is also sent per request; other devices cannot silently change this recording's mode.
            getSharedPreferences("style",MODE_PRIVATE).edit().putString("mode",mode).putString("target_language",target).commit();refresh();return true;
        });menu.show();
    }
    private void startRecording() {
        if(busy||protectedField)return;
        AppConfig config=AppConfig.load(this);
        if(PendingAudio.exists(this,config)){refresh();return;}
        if(!config.ready()||checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){setup();return;}
        try {
            recording=File.createTempFile("voice-",".m4a",getCacheDir());
            recorder=Build.VERSION.SDK_INT>=31?new MediaRecorder(this):new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);recorder.setAudioSamplingRate(16000);recorder.setAudioEncodingBitRate(64000);
            recorder.setOutputFile(recording.getAbsolutePath());recorder.prepare();recorder.start();
            recordingConfig=config;began=SystemClock.elapsedRealtime();recordingNow=true;pending=false;lastText="";Draft.clear();preview.setText("");refresh();main.post(tick);
        } catch(Exception e){cancelRecording();refresh();status.setText("無法錄音，請確認麥克風權限或其他 App 是否正在使用麥克風。");}
    }
    private void finishRecording() {
        if(!recordingNow)return;
        recordingNow=false;main.removeCallbacks(tick);
        File audio=recording;recording=null;
        AppConfig captured=recordingConfig;recordingConfig=null;
        try{recorder.stop();}catch(RuntimeException e){recorder.release();recorder=null;if(audio!=null)audio.delete();refresh();status.setText("錄音太短，請再說一次。");return;}
        recorder.release();recorder=null;
        if(audio==null){refresh();return;}
        if(captured==null||!captured.sameSession(AppConfig.load(this))){audio.delete();refresh();status.setText("登入或連線已變更，這段錄音未送出，請重新說話。");return;}
        process(audio,false,captured);
    }
    private void recoverLast() {
        if(busy||recordingNow||protectedField)return;
        if(pending){status.setText("請先插入或捨棄目前文字，再取回上一筆。");return;}
        if(getCurrentInputEditorInfo()!=null&&getPackageName().equals(getCurrentInputEditorInfo().packageName))return;
        process(null,false);
    }
    private void retryRecording(){if(!busy&&!recordingNow&&!protectedField&&!pending)process(null,true);}
    private void process(File audio,boolean retry){process(audio,retry,AppConfig.load(this));}
    private void process(File audio,boolean retry,final AppConfig config) {
        final long expected=generation,start=SystemClock.elapsedRealtime();
        busy=true;refresh();
        worker.execute(()->{
            VoiceApi.Result result=null;String error=null;
            VoiceApi.Progress progress=message->main.post(()->{if(!destroyed&&busy&&AppConfig.load(this).sameSession(config))status.setText(message);});
            try{
                if(!config.sameSession(AppConfig.load(this)))throw new java.io.IOException("登入或連線已變更，錄音未送出。");
                if(config.accountMode&&(audio!=null||retry)){
                    EncryptedRecording.Entry saved=retry?PendingAudio.read(this,config):PendingAudio.prepare(this,config,audio);
                    result=VoiceApi.upload(saved.requestConfig(config),saved.audio,saved.id,progress,retry);
                }else result=audio==null?VoiceApi.recover(config,progress):VoiceApi.upload(config,audio,progress);
                if(!result.id.isEmpty())PendingAudio.clearIfRequest(this,config,result.id);
            }catch(Exception e){error=VoiceApi.friendly(e);}finally{if(audio!=null)audio.delete();}
            final VoiceApi.Result done=result;final String problem=error;
            main.post(()->{
                if(destroyed)return;busy=false;
                if(!AppConfig.load(this).sameSession(config)){refresh();status.setText("帳號已切換，上一筆結果已清除。");return;}
                if(problem!=null){refresh();status.setText(problem+(retained?" 錄音已加密保留，可按重試或從「更多」刪除。":""));return;}
                lastText=done.text;pending=!lastText.trim().isEmpty();preview.setText(lastText);refresh();
                boolean inserted=false;
                if(audio!=null&&pending&&config.autoInsert&&generation==expected&&isInputViewShown()&&!protectedField)inserted=insertPending();
                String timing=String.format(Locale.TAIWAN,"%.1f 秒",(SystemClock.elapsedRealtime()-start)/1000.0);
                if(!done.warning.isEmpty())status.setText("排版暫時失敗，已保留辨識原文。"+(inserted?"已輸入。":"按插入可使用。"));
                else status.setText(lastText.trim().isEmpty()?"沒有辨識到語音，請再試一次。":(inserted?"已輸入　":done.mode.equals("translate")?"已翻成"+AppConfig.LANGUAGE_NAMES[AppConfig.languageIndex(done.targetLanguage)]+"，按插入　":"已整理，按插入　")+timing);
            });
        });
    }
    private boolean insertPending(){
        if(!pending||protectedField)return false;
        if(!AppConfig.load(this).sameSession(sessionConfig)){refresh();status.setText("登入或連線已變更，上一筆文字已清除。");return false;}
        InputConnection c=getCurrentInputConnection();if(c==null)return false;
        if(c.commitText(lastText,1)){pending=false;Draft.clear();refresh();status.setText("已插入，可以繼續說話。");return true;}return false;
    }
    private void cancelRecording(){closeLanguages();main.removeCallbacks(holdLanguage);main.removeCallbacks(repeatDelete);deleteHeld=false;languageGesture=false;main.removeCallbacks(tick);recordingNow=false;recordingConfig=null;if(recorder!=null){try{recorder.stop();}catch(Exception ignored){}recorder.release();recorder=null;}if(recording!=null){recording.delete();recording=null;}}
    @Override public void onDestroy(){destroyed=true;cancelRecording();worker.shutdownNow();main.removeCallbacksAndMessages(null);super.onDestroy();}
}
