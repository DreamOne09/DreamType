package tw.localvoice.keyboard;
/** Ephemeral editor handoff. Never write dictated text to preferences or logs. */
final class Draft {
 static String text=null;
 static boolean edited=false;
 static long revision=0;
 static void begin(String value){revision++;text=value;edited=false;}
 static void clear(){revision++;text=null;edited=false;}
}
