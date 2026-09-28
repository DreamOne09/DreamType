package tw.localvoice.keyboard;

import java.util.ArrayList;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** On-device wording alternatives. No transcript history or automatic changes. */
final class WordSuggestions {
 static final String[][] WORDS={
  {"軟件","軟體"},{"硬件","硬體"},{"鼠標","滑鼠"},{"打印機","印表機"},
  {"視頻","影片"},{"默認","預設"},{"文件夾","資料夾"},{"服務器","伺服器"},
  {"計劃","計畫"}
 };
 private static final Pattern PROTECTED=Pattern.compile("```[\\s\\S]*?```|`[^`\\n]*`|https?://[^\\s，。！？]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}|「[^」]*」|『[^』]*』|\"[^\"]*\"");
 static final class Suggestion {
  final int start,end;final String from,to;
  Suggestion(int start,String from,String to){this.start=start;this.end=start+from.length();this.from=from;this.to=to;}
  String label(){return from+" → "+to;}
 }
 static ArrayList<Suggestion> find(String text){
  ArrayList<Suggestion> found=new ArrayList<>();
  boolean[] protectedAt=new boolean[text.length()];Matcher matcher=PROTECTED.matcher(text);
  while(matcher.find())for(int i=matcher.start();i<matcher.end();i++)protectedAt[i]=true;
  for(String[] word:WORDS){
   int start=0;
   while((start=text.indexOf(word[0],start))>=0){
    boolean allowed=true;for(int i=start;i<start+word[0].length();i++)if(protectedAt[i])allowed=false;
    if(allowed)found.add(new Suggestion(start,word[0],word[1]));
    start+=word[0].length();
   }
  }
  found.sort((a,b)->Integer.compare(a.start,b.start));
  return found;
 }
}
