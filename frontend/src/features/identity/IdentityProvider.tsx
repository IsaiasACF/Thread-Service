import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getUser, userKey, type User } from './api';
import { errorCode, readError } from '../chat/errors';

export const IDENTITY_STORAGE_KEY = 'thread.identity.v1';
function readStoredId(): string {
  try {
    const value = JSON.parse(localStorage.getItem(IDENTITY_STORAGE_KEY) ?? 'null');
    return typeof value?.id === 'string' ? value.id : '';
  } catch { return ''; }
}
interface Identity {
  user: User | null; storedId: string; checking: boolean; error: string | null;
  storageWarning: string | null; choose: (user: User) => void; clear: () => void; refresh: () => void;
}
const Context = createContext<Identity | null>(null);
export function IdentityProvider({ children }: PropsWithChildren) {
  const [id, setId] = useState(readStoredId);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const cache = useQueryClient();
  const profile = useQuery({ queryKey: userKey(id), queryFn: ({ signal }) => getUser(id, signal),
    enabled: Boolean(id), staleTime: 60_000, retry: false, refetchOnMount: 'always' });
  const missing = Boolean(id) && ((profile.isSuccess && profile.data === null) || errorCode(profile.error) === 'NOT_FOUND');
  const persist = (value: string | null) => {
    try {
      if (value) localStorage.setItem(IDENTITY_STORAGE_KEY, JSON.stringify({ id: value }));
      else localStorage.removeItem(IDENTITY_STORAGE_KEY);
      setStorageWarning(null);
    } catch { setStorageWarning('El navegador no permite guardar la identidad. Solo estará disponible en esta sesión.'); }
  };
  useEffect(() => {
    if (missing) {
      try { localStorage.removeItem(IDENTITY_STORAGE_KEY); } catch { /* Keep the page usable. */ }
    }
  }, [missing]);
  const choose = (user: User) => {
    cache.setQueryData(userKey(user.id), user);
    persist(user.id);
    setId(user.id);
  };
  const clear = () => { persist(null); setId(''); };
  const error = missing ? 'La identidad guardada no existe. Selecciona otra identidad.'
    : profile.isError ? readError(profile.error) : null;
  return <Context.Provider value={{
    user: profile.isSuccess && !profile.isFetching && !missing ? profile.data ?? null : null,
    storedId: id, checking: Boolean(id) && profile.isFetching, error, storageWarning,
    choose, clear, refresh: () => { void profile.refetch(); },
  }}>{children}</Context.Provider>;
}
export function useIdentity() {
  const identity = useContext(Context);
  if (!identity) throw new Error('IdentityProvider is required');
  return identity;
}
