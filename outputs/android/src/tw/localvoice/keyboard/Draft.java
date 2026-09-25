package tw.localvoice.keyboard;
/** Ephemeral editor handoff. Never write dictated text to preferences or logs. */
final class Draft {
 static String text=null,rawText=null;
 static boolean edited=false;
 static long revision=0;
 static void begin(String value){begin(value,null);}
 static void begin(String value,String raw){revision++;text=value;rawText=raw;edited=false;}
 static void clear(){revision++;text=null;rawText=null;edited=false;}
}
