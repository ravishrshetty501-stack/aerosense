import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types/user';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, name?: string) => Promise<void>;
  logout: () => void;
  openAuthModal: () => void;
  closeAuthModal: () => void;
  isAuthModalOpen: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('aerosense_token'));
  const [loading, setLoading] = useState<boolean>(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);

  useEffect(() => {
    async function loadUser() {
      if (token) {
        try {
          const u = await api.getMe();
          setUser(u);
        } catch (e) {
          console.error('Failed to restore session:', e);
          localStorage.removeItem('aerosense_token');
          setToken(null);
          setUser(null);
        }
      }
      setLoading(false);
    }
    loadUser();
  }, [token]);

  const login = async (email: string, pass: string) => {
    const res = await api.login(email, pass);
    localStorage.setItem('aerosense_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    setIsAuthModalOpen(false);
  };

  const register = async (email: string, pass: string, name?: string) => {
    const res = await api.register({ email, password: pass, full_name: name });
    localStorage.setItem('aerosense_token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
    setIsAuthModalOpen(false);
  };

  const logout = () => {
    localStorage.removeItem('aerosense_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        openAuthModal: () => setIsAuthModalOpen(true),
        closeAuthModal: () => setIsAuthModalOpen(false),
        isAuthModalOpen,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};
