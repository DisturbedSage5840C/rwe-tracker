"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type { OrganizationRead, UserRead } from "@/lib/api";

type AuthState = {
  user: UserRead | null;
  org: OrganizationRead | null;
  accessToken: string | null;
  activeDrugId: string | null;
  setAuth: (payload: { user: UserRead; org: OrganizationRead | null; accessToken: string }) => void;
  setActiveDrug: (drugId: string | null) => void;
  clearAuth: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      org: null,
      accessToken: null,
      activeDrugId: null,
      setAuth: ({ user, org, accessToken }) => {
        set({ user, org, accessToken });
      },
      setActiveDrug: (drugId) => {
        set({ activeDrugId: drugId });
      },
      clearAuth: () => {
        set({ user: null, org: null, accessToken: null, activeDrugId: null });
      },
    }),
    {
      name: "rwe-auth-session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        org: state.org,
        accessToken: state.accessToken,
        activeDrugId: state.activeDrugId,
      }),
    },
  ),
);
