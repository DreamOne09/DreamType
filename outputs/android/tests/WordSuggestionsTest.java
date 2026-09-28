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
  System.out.println("PASS: wording suggestions preserve source and require per-occurrence acceptance");
 }
}
