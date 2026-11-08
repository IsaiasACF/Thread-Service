import { useQuery } from '@tanstack/react-query';
import { getUser, userKey } from '../identity/api';
import { useIdentity } from '../identity/IdentityProvider';

export function Author({ id }: { id: string }) {
  const identity = useIdentity();
  const author = useQuery({ queryKey: userKey(id), queryFn: ({ signal }) => getUser(id, signal),
    enabled: Boolean(id) && identity.user?.id !== id, staleTime: 5 * 60_000,
    retry: false, retryOnMount: false, refetchOnMount: false, refetchOnWindowFocus: false });
  return <strong title={id}>{identity.user?.id === id ? identity.user.displayName : author.data?.displayName ?? id}</strong>;
}
