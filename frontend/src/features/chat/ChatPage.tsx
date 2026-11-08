import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { useIdentity } from '../identity/IdentityProvider';
import { ThreadsPanel } from '../threads/ThreadsPanel';
import { channelKey, getChannel, getMessages, messagesKey, sendMessage, type Channel, type Message } from './api';
import { chronological, errorCode, readError } from './errors';
import { Composer } from './Composer';
import { MessageCard } from './MessageCard';
import { Workspace } from './Workspace';
import styles from './Chat.module.css';
import { useTimelineScroll } from './useTimelineScroll';

function Conversation({ channel }: { channel: Channel }) {
  const identity = useIdentity();
  const cache = useQueryClient();
  const [selected, setSelected] = useState<{ message: Message; trigger: HTMLElement | null } | null>(null);
  const key = messagesKey(channel.id);
  const messages = useQuery({ queryKey: key, queryFn: ({ signal }) => getMessages(channel.id, signal),
    staleTime: 0, refetchInterval: 5000, refetchIntervalInBackground: false, retry: false });
  const timeline = chronological(messages.data ?? []);
  const scroll = useTimelineScroll(timeline.at(-1)?.id);
  const refresh = () => { void messages.refetch(); };
  async function send(content: string) {
    if (!identity.user) throw new Error('No valid identity');
    const result = await sendMessage(channel.id, identity.user.id, content);
    await cache.cancelQueries({ queryKey: key, exact: true });
    scroll.revealNext();
    cache.setQueryData<Message[]>(key, old => chronological([...(old ?? []), result]));
    void cache.invalidateQueries({ queryKey: key, exact: true });
  }
  return <div className={styles.conversationLayout}>
    <section className={styles.conversation} aria-label={`Conversación de ${channel.name}`}>
      <header className={styles.conversationHeader}><div><span className={styles.eyebrow}>CONVERSACIÓN</span><h1><span aria-hidden="true">#</span> {channel.name}</h1></div>
        <button className={styles.textButton} onClick={refresh} disabled={messages.isFetching}>↻ Actualizar mensajes</button></header>
      {!identity.user && <p className={styles.identityBanner}>{identity.checking ? 'Validando tu identidad…' : <>Puedes leer la conversación. <Link to="/">Elige una identidad</Link> para participar.</>}</p>}
      <div ref={scroll.container} className={styles.messages} aria-label="Mensajes del canal" aria-busy={messages.isFetching}>
        {messages.isPending && <LoadingIndicator />}
        {messages.isError && <ErrorMessage message={readError(messages.error)} />}
        {messages.isSuccess && messages.data.length === 0 && <EmptyState>Este canal todavía no tiene mensajes. Comparte la primera idea.</EmptyState>}
        {timeline.map(message => <MessageCard key={message.id} message={message} selected={selected?.message.id === message.id} onReplies={() => setSelected({ message, trigger: document.activeElement as HTMLElement })} />)}
      </div>
      <Composer label="Nuevo mensaje" disabled={!identity.user} onSend={send} onRefresh={refresh} />
    </section>
    {selected && <ThreadsPanel key={selected.message.id} message={selected.message} returnFocus={selected.trigger} onClose={() => setSelected(null)} />}
  </div>;
}

function ChannelView({ id }: { id: string }) {
  const channel = useQuery({ queryKey: channelKey(id), queryFn: ({ signal }) => getChannel(id, signal),
    retry: false, staleTime: 0, refetchOnMount: 'always', refetchInterval: 30_000 });
  if (channel.isPending || (channel.isFetching && !channel.isFetchedAfterMount)) return <div className={styles.pageState}><LoadingIndicator /></div>;
  if (channel.isError && (!channel.data || errorCode(channel.error) === 'NOT_FOUND')) return <div className={styles.pageState}><h1>Canal no disponible</h1><ErrorMessage message={readError(channel.error)} /><button className={styles.textButton} onClick={() => { void channel.refetch(); }}>Reintentar canal</button></div>;
  if (!channel.data) return <div className={styles.pageState}><h1>Canal no disponible</h1><EmptyState>No encontramos el canal solicitado. Selecciona otro canal.</EmptyState></div>;
  return <>{channel.isError && <ErrorMessage message={readError(channel.error)} />}<Conversation key={id} channel={channel.data} /></>;
}
export default function ChatPage() {
  const { channelId } = useParams();
  return <Workspace>{channelId ? <ChannelView key={channelId} id={channelId} /> : <div className={styles.welcome}>
    <span className={styles.welcomeMark}>#</span><span className={styles.eyebrow}>BIENVENIDO A THREAD</span>
    <h1>Un canal para cada idea.</h1><p>Selecciona una conversación o crea un canal para empezar a compartir.</p>
    <p className={styles.intro}>Abre las respuestas de un mensaje para seguir el hilo sin perder el contexto.</p>
  </div>}</Workspace>;
}
