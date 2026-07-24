"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname } from "next/navigation";

import {
  ApiError,
  confirmEmailVerification,
  confirmPhoneVerification,
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "@/lib/auth-api-client";
import type {
  CurrentUser,
  LoginPayload,
  RegisterPayload,
  RegistrationResult,
  PhoneCodePayload,
} from "@/types/auth";

type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  sessionError: string | null;
  login: (payload: LoginPayload) => Promise<CurrentUser>;
  register: (payload: RegisterPayload) => Promise<RegistrationResult>;
  verifyPhone: (payload: PhoneCodePayload) => Promise<CurrentUser>;
  verifyEmail: (payload: PhoneCodePayload) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<CurrentUser | null>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

function requiresSessionCheck(pathname: string) {
  return !(
    pathname === "/" ||
    pathname === "/verifier-quittance" ||
    pathname.startsWith("/documents/")
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const checkSession = requiresSessionCheck(pathname);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setSessionError(null);
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (caughtError) {
      setUser(null);
      if (!(caughtError instanceof ApiError && caughtError.status === 403)) {
        setSessionError(
          caughtError instanceof Error
            ? caughtError.message
            : "Impossible de vérifier la session.",
        );
      }
      return null;
    } finally {
      setLoading(false);
      setSessionChecked(true);
    }
  }, []);

  useEffect(() => {
    if (!checkSession) return;

    let active = true;

    getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((caughtError) => {
        if (!active) return;
        setUser(null);
        if (!(caughtError instanceof ApiError && caughtError.status === 403)) {
          setSessionError(
            caughtError instanceof Error
              ? caughtError.message
              : "Impossible de vérifier la session.",
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
          setSessionChecked(true);
        }
      });

    return () => {
      active = false;
    };
  }, [checkSession]);

  const login = useCallback(async (payload: LoginPayload) => {
    const authenticatedUser = await loginUser(payload);
    setUser(authenticatedUser);
    setSessionError(null);
    return authenticatedUser;
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const result = await registerUser(payload);
    setSessionError(null);
    return result;
  }, []);

  const verifyPhone = useCallback(async (payload: PhoneCodePayload) => {
    const verifiedUser = await confirmPhoneVerification(payload);
    setUser(verifiedUser);
    setSessionError(null);
    return verifiedUser;
  }, []);

  const verifyEmail = useCallback(async (payload: PhoneCodePayload) => {
    const verifiedUser = await confirmEmailVerification(payload);
    setUser(verifiedUser);
    setSessionError(null);
    return verifiedUser;
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading: checkSession && (loading || !sessionChecked),
      sessionError,
      login,
      register,
      verifyPhone,
      verifyEmail,
      logout,
      refresh,
    }),
    [
      checkSession,
      login,
      logout,
      refresh,
      register,
      loading,
      sessionChecked,
      sessionError,
      user,
      verifyEmail,
      verifyPhone,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth doit être utilisé dans AuthProvider.");
  }
  return context;
}
