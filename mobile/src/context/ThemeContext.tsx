import { Appearance, useColorScheme } from "react-native";
import { useEffect, useState, type ReactNode } from "react";

import { applyScheme, getColorScheme, type ColorSchemeName } from "@/theme";

function resolvedScheme(system: string | null | undefined): ColorSchemeName {
  const fromAppearance = Appearance.getColorScheme();
  const value = fromAppearance ?? system;
  return value === "light" ? "light" : "dark";
}

/**
 * Follows the phone light/dark setting. Rebuilds themed styles before children
 * render so the first paint of a scheme change is already the new palette.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [, setTick] = useState(0);
  const scheme = resolvedScheme(system);
  if (getColorScheme() !== scheme) {
    applyScheme(scheme);
  }

  useEffect(() => {
    const sub = Appearance.addChangeListener(() => {
      setTick((n) => n + 1);
    });
    return () => sub.remove();
  }, []);

  return children;
}
