import { useState, useEffect } from 'react';
import AuthService, { AuthState } from '../services/AuthService';

export const useAuth = () => {
  const authService = AuthService.getInstance();
  const [authState, setAuthState] = useState<AuthState>(authService.getAuthState());

  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, [authService]);

  const signIn = async (username: string, password: string) => {
    return authService.signIn(username, password);
  };

  const signOut = async () => {
    return authService.signOut();
  };

  const signInWithHostedUI = () => {
    authService.signInWithHostedUI();
  };

  const getAccessToken = async () => {
    return authService.getAccessToken();
  };

  const getCredentials = async () => {
    return authService.getCredentials();
  };

  return {
    ...authState,
    signIn,
    signOut,
    signInWithHostedUI,
    getAccessToken,
    getCredentials,
  };
};