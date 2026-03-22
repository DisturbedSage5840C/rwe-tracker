"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type { OrganizationRead, UserRead } from "@/lib/api";

type AuthState = {
  user: UserRead | null;
  org: OrganizationRead | null;
  accessToken: string | null;
  activeDrugId: string | null;
  hydrated: boolean;
  setAuth: (payload: { user: UserRead; org: OrganizationRead | null; accessToken: string }) => void;
  setActiveDrug: (drugId: string | null) => void;
  clearAuth: () => void;
  setHydrated: (value: boolean) => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      org: null,
      accessToken: null,
      activeDrugId: null,
      hydrated: false,
      setAuth: ({ user, org, accessToken }) => {
        set({ user, org, accessToken });
      },
      setActiveDrug: (drugId) => {
        set({ activeDrugId: drugId });
      },
      clearAuth: () => {
        set({ user: null, org: null, accessToken: null, activeDrugId: null });
      },
      setHydrated: (value) => {
        set({ hydrated: value });
      },
    }),
    {
      name: "rwe-auth-session",
      storage: createJSONStorage(() => sessionStorage),
      skipHydration: true,
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
      partialize: (state) => ({
        user: state.user,
        org: state.org,
        accessToken: state.accessToken,
        activeDrugId: state.activeDrugId,
      }),
    },
  ),
);
