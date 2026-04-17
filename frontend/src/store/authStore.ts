import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthSession, User, UserRole } from '@/types';

interface AuthState {
  session: AuthSession | null;
  isAuthenticated: boolean;
  setSession: (session: AuthSession | null) => void;
  loginAsMock: (role: UserRole) => void;
  logout: () => void;
}

const MOCK_USERS: Record<UserRole, User> = {
  operator: { id: 'u-op', email: 'operator@geosentinel.app', name: 'Site Operator', role: 'operator' },
  esg_admin: { id: 'u-esg', email: 'admin@geosentinel.app', name: 'ESG Admin', role: 'esg_admin' },
  community: { id: 'u-com', email: 'community@geosentinel.app', name: 'Community Visitor', role: 'community' },
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      session: null,
      isAuthenticated: false,
      setSession: (session) => set({ session, isAuthenticated: !!session }),
      loginAsMock: (role) =>
        set({
          session: {
            access_token: `mock-${role}-token`,
            refresh_token: `mock-${role}-refresh`,
            user: MOCK_USERS[role],
          },
          isAuthenticated: true,
        }),
      logout: () => set({ session: null, isAuthenticated: false }),
    }),
    { name: 'gs.auth' },
  ),
);
