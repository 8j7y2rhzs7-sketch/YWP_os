import { activateKeepAwakeAsync, deactivateKeepAwake } from "expo-keep-awake";
import { useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";

const TAG = "ywp-os-foreground";
const RUN_TAG = "ywp-os-run";

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

/** Hold the display on for the whole time a run is on screen. */
export function useRunKeepAwake(active: boolean) {
  useEffect(() => {
    if (!active) return;
    activateKeepAwakeAsync(RUN_TAG).catch(() => undefined);
    return () => {
      deactivateKeepAwake(RUN_TAG).catch(() => undefined);
    };
  }, [active]);
}
