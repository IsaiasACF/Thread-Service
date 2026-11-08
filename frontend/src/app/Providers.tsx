import { useState, type PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function Providers({ children }: PropsWithChildren) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: false } },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
