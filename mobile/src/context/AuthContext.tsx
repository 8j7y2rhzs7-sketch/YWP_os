import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AppState, type AppStateStatus } from "react-native";

import { ApiError, loadApiUrl, rawRequest } from "@/lib/api";
import {
  clearStoredTokens,
  getStoredTokens,
  setStoredTokens,
} from "@/lib/storage";
import type { SubscriptionStatus, Tokens, User } from "@/types";

interface RegisterInput {
  email: string;
  password: string;
  name: string;
  timezone?: string;
}

interface AuthValue {
  user: User | null;
  tokens: Tokens | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (input: RegisterInput) => Promise<User>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<User>;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
}

const AuthContext = createContext<AuthValue | null>(null);

/** Re-check day-pass access while the app is open (matches server recheck TTL). */
const ACCESS_RESYNC_MS = 5 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const tokenRef = useRef<Tokens | null>(null);
  const rotateInFlight = useRef<Promise<Tokens> | null>(null);

  const saveTokens = useCallback(async (next: Tokens | null) => {
    tokenRef.current = next;
    setTokens(next);
    if (next) {
      await setStoredTokens(JSON.stringify(next));
    } else {
      await clearStoredTokens();
    }
  }, []);

  const rotate = useCallback(async (): Promise<Tokens> => {
    if (rotateInFlight.current) return rotateInFlight.current;
    const current = tokenRef.current;
    if (!current) {
      throw new ApiError("No refresh session is available", 401);
    }
    const pending = (async () => {
      const next = await rawRequest<Tokens>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      });
      await saveTokens(next);
      return next;
    })();
    rotateInFlight.current = pending;
    try {
      return await pending;
    } finally {
      if (rotateInFlight.current === pending) rotateInFlight.current = null;
    }
  }, [saveTokens]);

  const applyAccessLoss = useCallback((checkoutUrl?: string) => {
    setUser((current) => {
      if (!current) return current;
      return {
        ...current,
        has_app_access: false,
        subscription_status:
          current.subscription_status === "active"
            ? "inactive"
            : current.subscription_status,
        checkout_url: checkoutUrl ?? current.checkout_url ?? null,
      };
    });
  }, []);

  const request = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const current = tokenRef.current;
      if (!current) {
        throw new ApiError("Sign in is required", 401);
      }
      const run = (accessToken: string) => rawRequest<T>(path, init, accessToken);
      try {
        return await run(current.access_token);
      } catch (error) {
        if (error instanceof ApiError && error.status === 402) {
          applyAccessLoss(error.checkoutUrl);
          throw error;
        }
        if (!(error instanceof ApiError) || error.status !== 401) {
          throw error;
        }
        const next = await rotate();
        try {
          return await run(next.access_token);
        } catch (retryError) {
          if (retryError instanceof ApiError && retryError.status === 402) {
            applyAccessLoss(retryError.checkoutUrl);
          }
          throw retryError;
        }
      }
    },
    [applyAccessLoss, rotate],
  );

  const reloadUser = useCallback(async (): Promise<User> => {
    const profile = await request<User>("/users/me");
    setUser(profile);
    return profile;
  }, [request]);

  const syncAccess = useCallback(async (): Promise<User | null> => {
    if (!tokenRef.current) return null;
    try {
      const status = await request<SubscriptionStatus>("/whop/sync", {
        method: "POST",
      });
      const profile = await request<User>("/users/me");
      const merged: User = {
        ...profile,
        has_app_access: status.has_access,
        subscription_status: status.status,
        checkout_url: status.checkout_url,
        app_download_url: status.app_download_url ?? profile.app_download_url,
      };
      setUser(merged);
      return merged;
    } catch (error) {
      if (error instanceof ApiError && error.status === 402) {
        applyAccessLoss(error.checkoutUrl);
        return null;
      }
      // Fall back to profile refresh (server still TTL-checks on /users/me).
      try {
        return await reloadUser();
      } catch {
        return null;
      }
    }
  }, [applyAccessLoss, reloadUser, request]);

  const establish = useCallback(
    async (next: Tokens) => {
      await saveTokens(next);
      const profile = await rawRequest<User>(
        "/users/me",
        {},
        next.access_token,
      );
      setUser(profile);
      return profile;
    },
    [saveTokens],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const next = await rawRequest<Tokens>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      return establish(next);
    },
    [establish],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const next = await rawRequest<Tokens>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          ...input,
          email: input.email.trim().toLowerCase(),
          timezone: input.timezone ?? "America/New_York",
        }),
      });
      return establish(next);
    },
    [establish],
  );

  const logout = useCallback(async () => {
    const current = tokenRef.current;
    try {
      if (current) {
        await rawRequest("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: current.refresh_token }),
        });
      }
    } finally {
      setUser(null);
      await saveTokens(null);
    }
  }, [saveTokens]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await loadApiUrl();
        const stored = await getStoredTokens();
        if (!stored) return;
        const restored = JSON.parse(stored) as Tokens;
        tokenRef.current = restored;
        setTokens(restored);
        try {
          const profile = await rawRequest<User>(
            "/users/me",
            {},
            restored.access_token,
          );
          if (active) setUser(profile);
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            try {
              const next = await rotate();
              const profile = await rawRequest<User>(
                "/users/me",
                {},
                next.access_token,
              );
              if (active) setUser(profile);
              return;
            } catch (refreshError) {
              if (
                refreshError instanceof ApiError &&
                refreshError.status === 401
              ) {
                if (active) {
                  setUser(null);
                  await saveTokens(null);
                }
                return;
              }
              // Offline / timeout during refresh — keep stored session.
              if (active) setTokens(restored);
              return;
            }
          }
          // Network/timeout while offline — retain tokens for retry.
          if (active) setTokens(restored);
        }
      } catch {
        // Corrupt storage only.
        if (active) {
          setUser(null);
          await saveTokens(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [rotate, saveTokens]);

  useEffect(() => {
    if (!tokens) return;

    const onState = (state: AppStateStatus) => {
      if (state === "active") {
        void syncAccess();
      }
    };
    const sub = AppState.addEventListener("change", onState);
    const timer = setInterval(() => {
      if (AppState.currentState === "active") {
        void syncAccess();
      }
    }, ACCESS_RESYNC_MS);

    return () => {
      sub.remove();
      clearInterval(timer);
    };
  }, [syncAccess, tokens]);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      tokens,
      loading,
      login,
      register,
      logout,
      reloadUser,
      request,
    }),
    [user, tokens, loading, login, register, logout, reloadUser, request],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
