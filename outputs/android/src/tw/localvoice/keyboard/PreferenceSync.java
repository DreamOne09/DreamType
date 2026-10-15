package tw.localvoice.keyboard;

import java.io.IOException;
import org.json.JSONObject;

/** Save orchestration; storage must atomically recheck the expected session. */
final class PreferenceSync {
 interface Store {
  AppConfig current();
  void persist(AppConfig expected,JSONObject preferences,boolean auto)throws Exception;
 }
 interface Remote {void save(AppConfig expected,JSONObject preferences)throws Exception;}
 static void save(AppConfig expected,JSONObject preferences,boolean auto,Store store,Remote remote)throws Exception {
  if(!expected.sameSession(store.current()))
   throw new IOException("登入或連線已變更，請重新開啟頁面再操作。");
  if(expected.accountMode)remote.save(expected,preferences);
  // AppConfig guards this write under the same lock used by session changes.
  store.persist(expected,preferences,auto);
 }
}
