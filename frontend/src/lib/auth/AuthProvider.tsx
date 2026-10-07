"use client";

import Keycloak from "keycloak-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiFetch, type ApiRequest } from "@/lib/api/client";
import type { Role } from "@/lib/api/types";

interface AuthState {
  ready: boolean;
  authenticated: boolean;
  name: string;
  roles: Role[];
  login: () => void;
  logout: () => void;
  /** Authenticated API call; refreshes the access token when it is about to expire. */
  api: <T>(path: string, request?: Omit<ApiRequest, "token">) => Promise<T>;
}

const AuthContext = createContext<AuthState | null>(null);

let keycloak: Keycloak | null = null;
let initialization: Promise<boolean> | null = null;

// keycloak-js may only be initialised once per page; React strict mode runs
// effects twice in development, so the promise is shared at module level.
function initKeycloak(): Promise<boolean> {
  if (!initialization) {
    keycloak = new Keycloak({
      url: process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8080",
      realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "kalinowo",
      clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "uni-web",
    });
    initialization = keycloak
      .init({ onLoad: "check-sso", pkceMethod: "S256", checkLoginIframe: false })
      .catch(() => false);
  }
  return initialization;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let active = true;
    initKeycloak().then((isAuthenticated) => {
      if (!active) return;
      setAuthenticated(isAuthenticated);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const api = useCallback(
    async <T,>(path: string, request: Omit<ApiRequest, "token"> = {}): Promise<T> => {
      if (!keycloak?.authenticated) throw new Error("Not signed in");
      await keycloak.updateToken(30);
      return apiFetch<T>(path, { ...request, token: keycloak.token });
    },
    [],
  );

  const value = useMemo<AuthState>(() => {
    const claims = authenticated ? keycloak?.tokenParsed : undefined;
    return {
      ready,
      authenticated,
      name: (claims?.name as string | undefined) ?? "",
      roles: (claims?.realm_access?.roles ?? []) as Role[],
      login: () => void keycloak?.login(),
      logout: () => void keycloak?.logout({ redirectUri: window.location.origin }),
      api,
    };
  }, [ready, authenticated, api]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function hasAnyRole(roles: Role[], allowed: Role[]): boolean {
  return roles.includes("admin") || allowed.some((role) => roles.includes(role));
}
