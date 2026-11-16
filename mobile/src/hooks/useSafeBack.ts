import { router, type Href } from "expo-router";
import { useCallback, useEffect } from "react";
import { BackHandler } from "react-native";

const HOME: Href = "/(tabs)";

/**
 * In-app + Android hardware back that never exits the app from a restored
 * stack screen with an empty history. Falls back to Home (or a custom href).
 */
export function useSafeBack(fallback: Href = HOME) {
  const goBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
      return;
    }
    router.replace(fallback);
  }, [fallback]);

  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      goBack();
      return true;
    });
    return () => sub.remove();
  }, [goBack]);

  return goBack;
}
