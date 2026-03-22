"use client";

import { useEffect } from "react";
import { Toaster } from "sonner";

import { useAuthStore } from "@/lib/store/auth-store";

const AUTH_INVALID_EVENT = "rwe:auth-invalid";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    let active = true;
    let fallbackTimer: ReturnType<typeof setTimeout> | null = null;

    const completeHydration = () => {
      if (active) {
        useAuthStore.getState().setHydrated(true);
      }
    };

    // Prevent indefinite loading screens if persist hydration stalls in the browser.
    fallbackTimer = setTimeout(() => {
      completeHydration();
    }, 1500);

    const persistApi = useAuthStore.persist;
    const unsubscribeFinish = persistApi?.onFinishHydration?.(() => {
      completeHydration();
    });

    const clearCorruptedSession = () => {
      try {
        const raw = window.sessionStorage.getItem("rwe-auth-session");
        if (!raw) {
          return;
        }
        JSON.parse(raw);
      } catch {
        window.sessionStorage.removeItem("rwe-auth-session");
      }
    };

    if (persistApi?.hasHydrated?.()) {
      completeHydration();
    } else {
      Promise.resolve(persistApi?.rehydrate?.())
        .catch(() => {
          clearCorruptedSession();
          return Promise.resolve(persistApi?.rehydrate?.()).catch(() => {
            completeHydration();
          });
        })
        .finally(() => {
          completeHydration();
        });
    }

    const onAuthInvalid = async () => {
      useAuthStore.getState().clearAuth();
      try {
        await fetch("/api/auth/session", { method: "DELETE" });
      } catch {
        // Best effort cookie cleanup.
      }
      if (window.location.pathname !== "/login") {
        window.location.assign("/login?expired=1");
      }
    };

    window.addEventListener(AUTH_INVALID_EVENT, onAuthInvalid);

    return () => {
      active = false;
      if (fallbackTimer) {
        clearTimeout(fallbackTimer);
      }
      unsubscribeFinish?.();
      window.removeEventListener(AUTH_INVALID_EVENT, onAuthInvalid);
    };
  }, []);

  return (
    <>
      {children}
      <Toaster richColors position="top-right" />
    </>
  );
}
