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

import { ApiError, loadApiUrl, rawRequest } from "@/lib/api";
import {
  clearStoredTokens,
  getStoredTokens,
  setStoredTokens,
} from "@/lib/storage";
import type { Tokens, User } from "@/types";

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
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<User>;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokens] = useState<Tokens | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const tokenRef = useRef<Tokens | null>(null);

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
    const current = tokenRef.current;
    if (!current) {
      throw new ApiError("No refresh session is available", 401);
    }
    const next = await rawRequest<Tokens>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: current.refresh_token }),
    });
    await saveTokens(next);
    return next;
  }, [saveTokens]);

  const request = useCallback(
    async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
      const current = tokenRef.current;
      if (!current) {
        throw new ApiError("Sign in is required", 401);
      }
      try {
        return await rawRequest<T>(path, init, current.access_token);
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) {
          throw error;
        }
        const next = await rotate();
        return rawRequest<T>(path, init, next.access_token);
      }
    },
    [rotate],
  );

  const reloadUser = useCallback(async (): Promise<User> => {
    const profile = await request<User>("/users/me");
    setUser(profile);
    return profile;
  }, [request]);

  const establish = useCallback(
    async (next: Tokens) => {
      await saveTokens(next);
      const profile = await rawRequest<User>(
        "/users/me",
        {},
        next.access_token,
      );
      setUser(profile);
    },
    [saveTokens],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const next = await rawRequest<Tokens>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      await establish(next);
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
      await establish(next);
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
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          const next = await rotate();
          const profile = await rawRequest<User>(
            "/users/me",
            {},
            next.access_token,
          );
          if (active) setUser(profile);
        }
      } catch {
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
