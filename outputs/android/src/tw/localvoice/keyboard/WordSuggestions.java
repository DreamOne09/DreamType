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
 private static final Pattern PROTECTED=Pattern.compile("```[\\s\\S]*?(?:```|$)|`[^`\\n]*(?:`|$)|https?://[^\\s，。！？；：、（）「」『』“”《》\"]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}");
 // Scan paired delimiters so nested and unfinished quotations stay literal.
 private static void protectQuotes(String text,boolean[] protectedAt){
  String open="「『“‘《〈\"",close="」』”’》〉\"";
  ArrayList<Character> stack=new ArrayList<>();int begin=-1;
  for(int i=0;i<text.length();i++){
   if(protectedAt[i])continue;
   char c=text.charAt(i);
   if(c=='"'){
    int slashes=0;for(int j=i-1;j>=0&&text.charAt(j)=='\\';j--)slashes++;
    if(slashes%2==1)continue;
   }
   if(!stack.isEmpty()&&c==stack.get(stack.size()-1)){
    stack.remove(stack.size()-1);
    if(stack.isEmpty()){for(int j=begin;j<=i;j++)protectedAt[j]=true;begin=-1;}
   }else{
    int kind=open.indexOf(c);
    if(kind>=0){if(stack.isEmpty())begin=i;stack.add(close.charAt(kind));}
   }
  }
  if(begin>=0)for(int i=begin;i<text.length();i++)protectedAt[i]=true;
 }
 static final class Suggestion {
  final int start,end;final String from,to;
  Suggestion(int start,String from,String to){this.start=start;this.end=start+from.length();this.from=from;this.to=to;}
  String label(){return from+" → "+to;}
 }
 static String validate(String value){
  if(value==null||value.length()>1000)throw new IllegalArgumentException("用詞對照最多 1,000 字。");
  ArrayList<String> result=new ArrayList<>();java.util.HashSet<String> seen=new java.util.HashSet<>();
  for(String line:value.split("\\n")){
   line=line.trim();if(line.isEmpty())continue;
   String[] parts=line.split("→",-1);
   if(parts.length!=2)throw new IllegalArgumentException("每行請使用「原詞 → 慣用寫法」。");
   String from=parts[0].trim(),to=parts[1].trim();
   if(from.isEmpty()||to.isEmpty()||from.length()>40||to.length()>40)throw new IllegalArgumentException("對照兩側都要填寫，每側最多 40 字。");
   if(from.equals(to)||!seen.add(from))throw new IllegalArgumentException("原詞不可重複，兩側不可相同。");
   for(char c:(from+to).toCharArray())if(c<32)throw new IllegalArgumentException("用詞不可包含控制字元。");
   result.add(from+" → "+to);
  }
  if(result.size()>20)throw new IllegalArgumentException("最多設定 20 組用詞對照。");
  return String.join("\n",result);
 }
 private static boolean asciiWord(char c){return c>='a'&&c<='z'||c>='A'&&c<='Z'||c>='0'&&c<='9'||c=='_';}
 static ArrayList<Suggestion> find(String text){return find(text,"");}
 static ArrayList<Suggestion> find(String text,String rules){
  ArrayList<Suggestion> found=new ArrayList<>();
  ArrayList<String[]> words=new ArrayList<>();java.util.HashSet<String> personal=new java.util.HashSet<>();
  try{for(String line:validate(rules).split("\n"))if(!line.isEmpty()){
   String[] pair=line.split(" → ",-1);words.add(pair);personal.add(pair[0]);
  }}catch(IllegalArgumentException invalid){words.clear();personal.clear();}
  words.sort((a,b)->Integer.compare(b[0].length(),a[0].length()));
  for(String[] word:WORDS)if(!personal.contains(word[0]))words.add(word);
  boolean[] protectedAt=new boolean[text.length()];Matcher matcher=PROTECTED.matcher(text);
  while(matcher.find())for(int i=matcher.start();i<matcher.end();i++)protectedAt[i]=true;
  protectQuotes(text,protectedAt);
  for(String[] word:words){
   int start=0;
   while((start=text.indexOf(word[0],start))>=0){
    boolean allowed=true;for(int i=start;i<start+word[0].length();i++)if(protectedAt[i])allowed=false;
    int end=start+word[0].length();
    if(asciiWord(word[0].charAt(0))&&start>0&&asciiWord(text.charAt(start-1)))allowed=false;
    if(asciiWord(word[0].charAt(word[0].length()-1))&&end<text.length()&&asciiWord(text.charAt(end)))allowed=false;
    if(allowed){found.add(new Suggestion(start,word[0],word[1]));for(int i=start;i<end;i++)protectedAt[i]=true;}
    start+=word[0].length();
   }
  }
  found.sort((a,b)->Integer.compare(a.start,b.start));
  return found;
 }
}
