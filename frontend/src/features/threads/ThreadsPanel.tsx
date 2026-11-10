import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { useIdentity } from '../identity/IdentityProvider';
import { createReply, getReplies, repliesKey, type Message, type Reply } from '../chat/api';
import { chronological, errorCode, readError } from '../chat/errors';
import { Composer } from '../chat/Composer';
import { MessageCard } from '../chat/MessageCard';
import styles from '../chat/Chat.module.css';
import { useTimelineScroll } from '../chat/useTimelineScroll';

export function ThreadsPanel({ message, onClose, returnFocus }: { message: Message; onClose: () => void; returnFocus?: HTMLElement | null }) {
  const identity = useIdentity();
  const cache = useQueryClient();
  const panel = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose); onCloseRef.current = onClose;
  const [mobile, setMobile] = useState(() => window.matchMedia?.('(max-width: 1100px)').matches ?? false);
  useEffect(() => {
    const media = window.matchMedia?.('(max-width: 1100px)');
    const update = () => setMobile(media?.matches ?? false);
    media?.addEventListener('change', update);
    return () => media?.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const previous = returnFocus ?? document.activeElement as HTMLElement | null;
    close.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
      if (event.key === 'Tab' && window.matchMedia?.('(max-width: 1100px)').matches) {
        const nodes = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], textarea:not(:disabled), input:not(:disabled)');
        if (!nodes?.length) return;
        const first = nodes[0], last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); if (previous?.isConnected) previous.focus(); };
  }, []);
  const key = repliesKey(message.channelId, message.id);
  const replies = useQuery({ queryKey: key, queryFn: ({ signal }) => getReplies(message.channelId, message.id, signal),
    retry: false, staleTime: 0, refetchInterval: 5000, refetchIntervalInBackground: false });
  const timeline = chronological(replies.data ?? []);
  const scroll = useTimelineScroll(timeline.at(-1)?.id);
  const refresh = () => { void replies.refetch(); };
  async function send(content: string) {
    if (!identity.user) throw new Error('No valid identity');
    const result = await createReply(message.channelId, message.id, identity.user.id, content);
    await cache.cancelQueries({ queryKey: key, exact: true });
    scroll.revealNext();
    cache.setQueryData<Reply[]>(key, old => chronological([...(old ?? []), result]));
    void cache.invalidateQueries({ queryKey: key, exact: true });
  }
  return <>
    <div className={styles.backdrop} onClick={onClose} aria-hidden="true" />
    <aside className={styles.threadPanel} ref={panel} role="dialog" aria-label="Respuestas del mensaje" aria-modal={mobile || undefined}>
      <header className={styles.threadHeader}><h2>Respuestas</h2><button ref={close} className={styles.iconButton} aria-label="Cerrar respuestas" onClick={onClose}>Cerrar</button></header>
      <div ref={scroll.container} className={styles.threadBody}>
        <h3 className={styles.sectionLabel}>Mensaje original</h3><MessageCard message={message} />
        <div className={styles.threadDivider}><h3>Conversación del hilo</h3><button className={styles.textButton} onClick={refresh} disabled={replies.isFetching}>Actualizar respuestas</button></div>
        {replies.isPending && <LoadingIndicator />}
        {replies.isError && <ErrorMessage message={errorCode(replies.error) === 'NOT_FOUND' ? 'El mensaje original ya no está disponible.' : readError(replies.error)} />}
        {replies.isSuccess && replies.data.length === 0 && <EmptyState>Aún no hay respuestas. Sé la primera persona en responder.</EmptyState>}
        {timeline.map(reply => <MessageCard key={reply.id} message={reply} />)}
      </div>
      <Composer reply label="Tu respuesta" disabled={!identity.user || errorCode(replies.error) === 'NOT_FOUND'} onSend={send} onRefresh={refresh} />
    </aside>
  </>;
}
