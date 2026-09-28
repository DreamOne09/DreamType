package tw.localvoice.keyboard;

public final class WordSuggestionsTest {
 public static void main(String[] args){
  String text="這個軟件需要硬件支援，軟件不必更新。";
  java.util.ArrayList<WordSuggestions.Suggestion> found=WordSuggestions.find(text);
  if(found.size()!=3)throw new AssertionError("Find repeated occurrences separately");
  WordSuggestions.Suggestion first=found.get(0);
  String applied=text.substring(0,first.start)+first.to+text.substring(first.end);
  if(!applied.equals("這個軟體需要硬件支援，軟件不必更新。"))throw new AssertionError("Only selected occurrence may change");
  if(!WordSuggestions.find("保留「軟件」和 `硬件`，https://example.com/視頻").isEmpty())throw new AssertionError("Protect quotes, code and URLs");
  if(!WordSuggestions.find("請幫我生成一個計畫。明天不要取消。").isEmpty())throw new AssertionError("Never invent tasks or suggestions");
  if(!WordSuggestions.find("").isEmpty())throw new AssertionError("Empty input");
  String rules="夢想型態 → DreamType\nGPT → ChatGPT\n軟件 → 應用程式\n軟件平台 → 應用平台";
  found=WordSuggestions.find("夢想型態使用GPT，ChatGPT與GPT4不用改。軟件平台和軟件。",rules);
  if(found.size()!=4||!found.get(0).to.equals("DreamType")||!found.get(2).to.equals("應用平台")||!found.get(3).to.equals("應用程式"))throw new AssertionError("Personal, longest nonoverlapping alternatives; ASCII word boundaries");
  if(!WordSuggestions.find("「夢想型態」 `GPT` https://x.test/GPT",rules).isEmpty())throw new AssertionError("Personal rules preserve protected literals");
  if(!WordSuggestions.find("夢想型態","").isEmpty())throw new AssertionError("Removing personal rule stops suggestions");
  if(!WordSuggestions.find("夢想型態", "malformed").isEmpty())throw new AssertionError("Invalid stored rules fail closed");
  for(String invalid:new String[]{"a → a","a → b\na → c","a → b → c","a →","a\tb → c"}){
   try{WordSuggestions.validate(invalid);throw new AssertionError("Invalid rule accepted");}catch(IllegalArgumentException expected){}
  }
  if(!WordSuggestions.validate(" 汐只→汐止 \n").equals("汐只 → 汐止"))throw new AssertionError("Canonical rules");
  System.out.println("PASS: wording suggestions preserve source and require per-occurrence acceptance");
 }
}
