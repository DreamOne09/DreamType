package tw.localvoice.keyboard;

/** UI-thread ownership gate; only a fresh successful Play query can clear ownership. */
final class PurchaseState {
 private long revision;
 private boolean known,owned;
 long beginQuery(){known=false;return revision;}
 void observedPurchase(){revision++;owned=true;known=false;}
 boolean applyQuery(long startedAt,int count){
  if(startedAt!=revision)return false;
  known=true;owned=count>0;return true;
 }
 boolean known(){return known;}
 boolean owned(){return owned;}
}
