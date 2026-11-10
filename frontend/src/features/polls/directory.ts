import { getMessages } from '../chat/api';
import { errorCode } from '../chat/errors';
import type { Poll } from './api';

export const sessionPollsKey = ['poll-directory-session'] as const;
const MAX_REFERENCES = 25;
const UUID = '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}';
const reference = new RegExp(`(?:^|\\n)Poll ID: (${UUID})(?:\\r?\\n|$)`, 'i');

export async function discoverPolls(channelId: string, fetchPoll: (id: string) => Promise<Poll | null>, signal?: AbortSignal) {
  const messages = await getMessages(channelId, signal);
  const ids = [...new Set([...messages].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .flatMap(message => message.channelId === channelId ? [reference.exec(message.content)?.[1]?.toLowerCase()].filter((id): id is string => Boolean(id)) : []))];
  const selected = ids.slice(0, MAX_REFERENCES);
  const items: Poll[] = [];
  let next = 0;
  let failures = 0;
  let firstError: unknown;
  // Bound discovery requests; don't load every channel or trust the announcement's title/state.
  await Promise.all(Array.from({ length: Math.min(3, selected.length) }, async () => {
    while (next < selected.length) {
      if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
      const id = selected[next++];
      try {
        const poll = await fetchPoll(id);
        if (poll?.channelId === channelId) items.push(poll);
      } catch (error) {
        if (signal?.aborted) throw error;
        if (errorCode(error) !== 'NOT_FOUND') { failures++; firstError ??= error; }
      }
    }
  }));
  if (failures === selected.length && failures > 0) throw firstError;
  return { items, failures, truncated: ids.length > MAX_REFERENCES };
}

export function mergePolls(...groups: Poll[][]): Poll[] {
  return [...new Map(groups.flat().map(poll => [poll.pollId, poll])).values()]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || a.pollId.localeCompare(b.pollId));
}
