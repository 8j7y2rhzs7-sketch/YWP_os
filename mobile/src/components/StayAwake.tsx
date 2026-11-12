import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";
import { useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";

const TAG = "ywp-os-foreground";

/**
 * Keep the display on while YWP OS is the app on screen.
 * A background service would still go blank when the phone sleeps, which is
 * the reopen loop. Releasing the lock in the background lets the phone sleep
 * after the user leaves.
 */
export function StayAwake() {
  useEffect(() => {
    const sync = (state: AppStateStatus) => {
      if (state === "background") {
        deactivateKeepAwake(TAG).catch(() => undefined);
        return;
      }
      activateKeepAwakeAsync(TAG).catch(() => undefined);
    };
    sync(AppState.currentState);
    const sub = AppState.addEventListener("change", sync);
    return () => {
      sub.remove();
      deactivateKeepAwake(TAG).catch(() => undefined);
    };
  }, []);
  return null;
}
