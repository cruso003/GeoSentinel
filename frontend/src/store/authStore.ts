import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthSession, User, UserRole } from '@/types';
import { api, ApiError } from '@/api/client';

interface AuthState {
  session: AuthSession | null;
  isAuthenticated: boolean;
  loginError: string | null;
  loginPending: boolean;
  setSession: (session: AuthSession | null) => void;
  loginAsMock: (role: UserRole) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
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
      loginError: null,
      loginPending: false,
      setSession: (session) => set({ session, isAuthenticated: !!session }),
      loginAsMock: (role) =>
        set({
          session: {
            access_token: `mock-${role}-token`,
            refresh_token: `mock-${role}-refresh`,
            user: MOCK_USERS[role],
          },
          isAuthenticated: true,
          loginError: null,
        }),
      login: async (email, password) => {
        set({ loginPending: true, loginError: null });
        try {
          const res = await api.post<AuthSession>('/auth/login', { email, password });
          set({ session: res, isAuthenticated: true, loginPending: false });
        } catch (err) {
          const message =
            err instanceof ApiError && err.status === 401
              ? 'Invalid email or password.'
              : err instanceof Error
                ? err.message
                : 'Login failed.';
          set({ loginError: message, loginPending: false });
          throw err;
        }
      },
      logout: async () => {
        const session = useAuthStore.getState().session;
        if (session?.refresh_token && !session.refresh_token.startsWith('mock-')) {
          try {
            await api.post('/auth/logout', { refresh_token: session.refresh_token });
          } catch {
            // Best-effort — always clear client state even if the server
            // rejects (expired token, network hiccup, etc.).
          }
        }
        set({ session: null, isAuthenticated: false, loginError: null });
      },
    }),
    { name: 'gs.auth' },
  ),
);
