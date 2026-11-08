import { afterEach, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { buildSchema, parse, validate } from 'graphql';
declare const __CHAT_CONTRACT__: string;
import { App } from '../../app/App';
import { IDENTITY_STORAGE_KEY } from '../identity/IdentityProvider';
import type { User } from '../identity/api';
import type { Channel, Message, Reply } from './api';

const schema = buildSchema(__CHAT_CONTRACT__);
export interface Call { operation: string; variables: Record<string, string>; signal?: AbortSignal }
export interface Store { users: User[]; channels: Channel[]; messages: Message[]; replies: Reply[] }
export type Handler = (call: Call, store: Store) => Response | Promise<Response>;
const caches: QueryClient[] = [];
afterEach(() => { caches.forEach(cache => cache.clear()); caches.length = 0; vi.restoreAllMocks(); localStorage.clear(); });
export function savedIdentity(id = 'u-1') { localStorage.setItem(IDENTITY_STORAGE_KEY, JSON.stringify({ id })); }
export function json(data: unknown) { return new Response(JSON.stringify({ data }), { headers: { 'Content-Type': 'application/json' } }); }
export function error(code: string, service = 'messages') {
  return new Response(JSON.stringify({ data: null, errors: [{ message: 'private upstream detail', extensions: { code, service } }] }), { headers: { 'Content-Type': 'application/json' } });
}
export function backend(overrides: Record<string, Handler> = {}) {
  const store: Store = {
    users: [{ id: 'u-1', displayName: 'Ana' }, { id: 'u-2', displayName: 'Bruno' }],
    channels: [{ id: 'c-1', name: 'general' }, { id: 'c-2', name: 'proyecto' }],
    messages: [
      { id: 'm-2', channelId: 'c-1', authorId: 'u-2', content: 'Después', createdAt: '2026-11-08T11:00:00Z' },
      { id: 'm-1', channelId: 'c-1', authorId: 'u-2', content: 'Primero\nSegunda línea', createdAt: '2026-11-08T10:00:00Z' },
      { id: 'm-3', channelId: 'c-2', authorId: 'u-1', content: 'Otro canal', createdAt: '2026-11-08T12:00:00Z' },
    ], replies: [],
  };
  const calls: Call[] = [];
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input));
    expect(url.pathname).toBe('/graphql');
    expect(url.origin).toBe(window.location.origin);
    const body = JSON.parse(String(init?.body));
    expect(validate(schema, parse(body.query))).toEqual([]);
    const call: Call = { operation: /(?:query|mutation)\s+(\w+)/.exec(body.query)?.[1] ?? '', variables: body.variables ?? {}, signal: init?.signal ?? undefined };
    calls.push(call);
    if (overrides[call.operation]) return overrides[call.operation](call, store);
    const v = call.variables;
    switch (call.operation) {
      case 'GetUser': return json({ user: store.users.find(user => user.id === v.id) ?? null });
      case 'CreateUser': { const user = { id: 'u-created', displayName: v.name }; store.users.push(user); return json({ createUser: user }); }
      case 'GetChannels': return json({ channels: store.channels });
      case 'GetChannel': return json({ channel: store.channels.find(channel => channel.id === v.id) ?? null });
      case 'CreateChannel': { const channel = { id: 'c-created', name: v.name }; store.channels.push(channel); return json({ createChannel: channel }); }
      case 'GetMessages': return json({ messages: store.messages.filter(message => message.channelId === v.channelId) });
      case 'SendMessage': { const message = { id: 'm-created', channelId: v.channelId, authorId: v.authorId, content: v.content, createdAt: '2026-11-08T13:00:00Z' }; store.messages.push(message); return json({ sendMessage: message }); }
      case 'GetReplies': return json({ replies: store.replies.filter(reply => reply.channelId === v.channelId && reply.messageId === v.messageId) });
      case 'CreateReply': { const reply = { id: 'r-created', channelId: v.channelId, messageId: v.messageId, authorId: v.authorId, content: v.content, createdAt: '2026-11-08T14:00:00Z' }; store.replies.push(reply); return json({ createReply: reply }); }
      default: throw new Error(`Unexpected operation ${call.operation}`);
    }
  });
  return { store, calls, fetch };
}
export function mount(path = '/') {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  caches.push(cache);
  const view = render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
  return { ...view, cache };
}
