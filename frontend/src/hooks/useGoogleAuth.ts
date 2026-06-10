/**
 * useGoogleAuth Hook
 * ------------------
 * Initialises the Google Identity Services (GIS) library and provides a
 * `signInWithGoogle()` function that opens the credential selection popup.
 *
 * Design decisions:
 *  - GIS is initialised lazily on first call (not on mount) to avoid blocking.
 *  - The hook never stores the Google ID token — it's immediately exchanged for
 *    a backend JWT, which is what's persisted in localStorage.
 *  - All errors surface as thrown Error objects so callers can display them.
 *  - TypeScript `window.google` types come from the @types/google.accounts stub
 *    or are declared inline here to avoid a dev dependency.
 */
import { useCallback } from 'react';
import { apiClient } from '../api/client';

// GIS global type stub (avoids installing @types/google.accounts)
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          prompt: () => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, unknown>
          ) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string;

export interface GoogleAuthResult {
  access_token: string;
  token_type: string;
  auth_provider: 'google';
}

/**
 * Returns a `signInWithGoogle` function.
 * Call it on a button click — it opens the GIS popup and resolves with
 * the backend JWT when the user successfully authenticates.
 */
export function useGoogleAuth() {
  const signInWithGoogle = useCallback((): Promise<GoogleAuthResult> => {
    return new Promise((resolve, reject) => {
      if (!GOOGLE_CLIENT_ID) {
        reject(new Error('VITE_GOOGLE_CLIENT_ID is not set in frontend .env'));
        return;
      }

      if (!window.google?.accounts?.id) {
        reject(
          new Error(
            'Google Identity Services not loaded. ' +
            'Ensure the GIS script tag is present in index.html.'
          )
        );
        return;
      }

      // Initialise GIS with a one-shot callback
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          if (!response.credential) {
            reject(new Error('Google sign-in was cancelled or failed.'));
            return;
          }

          try {
            // Exchange Google ID token for our backend JWT
            const res = await apiClient.post<GoogleAuthResult>('/auth/google', {
              id_token: response.credential,
            });
            resolve(res.data);
          } catch (err: unknown) {
            const msg =
              (err as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail ??
              'Google authentication failed. Please try again.';
            reject(new Error(msg));
          }
        },
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      // Open the One Tap / popup selector
      window.google.accounts.id.prompt();
    });
  }, []);

  return { signInWithGoogle };
}
