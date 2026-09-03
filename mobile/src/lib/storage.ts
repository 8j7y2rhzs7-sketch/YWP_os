import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const TOKEN_KEY = "ywp.os.tokens.v3";

export async function getStoredTokens(): Promise<string | null> {
  if (Platform.OS === "web") {
    return typeof localStorage === "undefined"
      ? null
      : localStorage.getItem(TOKEN_KEY);
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setStoredTokens(value: string): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(TOKEN_KEY, value);
    }
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

export async function clearStoredTokens(): Promise<void> {
  if (Platform.OS === "web") {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
    }
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
