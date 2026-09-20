package tw.localvoice.keyboard;
/** Ephemeral editor handoff. Never write dictated text to preferences or logs. */
final class Draft {
 static String text=null;
 static boolean edited=false;
 static void begin(String value){text=value;edited=false;}
 static void clear(){text=null;edited=false;}
}
