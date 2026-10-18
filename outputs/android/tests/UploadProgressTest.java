package tw.localvoice.keyboard;

import java.io.*;
import java.util.*;

public final class UploadProgressTest {
    public static void main(String[] args)throws Exception {
        byte[] audio=new byte[700001];new Random(7).nextBytes(audio);
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        List<String> updates=new ArrayList<>();
        VoiceApi.writeAudio(out,audio,updates::add);
        if(!Arrays.equals(audio,out.toByteArray()))throw new AssertionError("Changed upload bytes");
        if(updates.size()<2||updates.size()>10||new HashSet<>(updates).size()!=updates.size())throw new AssertionError("Unbounded or duplicated progress");
        if(updates.stream().anyMatch(s->s.contains("100%")||s.contains("完成")))throw new AssertionError("Premature success");
        List<String> failed=new ArrayList<>();
        OutputStream broken=new OutputStream(){
            public void write(int b)throws IOException{throw new IOException("synthetic failure");}
            public void write(byte[] b,int offset,int length)throws IOException{throw new IOException("synthetic failure");}
        };
        try{VoiceApi.writeAudio(broken,audio,failed::add);throw new AssertionError("Swallowed upload failure");}
        catch(IOException expected){}
        if(!failed.isEmpty())throw new AssertionError("Reported unwritten bytes");
        VoiceApi.writeAudio(new ByteArrayOutputStream(),new byte[0],failed::add);
        if(!failed.isEmpty())throw new AssertionError("Invented empty upload progress");
        System.out.println("PASS: upload bytes, bounded progress and transport failure");
    }
}
