import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Button, EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { channelsKey, getChannels } from '../chat/api';
import { readError } from '../chat/errors';
import { getPoll, type Poll } from './api';
import { discoverPolls, mergePolls, sessionPollsKey } from './directory';
import styles from './Polls.module.css';

const states: Record<Poll['status'], string> = { open: 'Abierta', closed: 'Cerrada', pending_announcement: 'Pendiente', creation_failed: 'No se pudo publicar' };

export function PollDirectory({ currentPoll, initialChannel = '' }: { currentPoll?: Poll | null; initialChannel?: string }) {
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [channel, setChannel] = useState(initialChannel);
  const [status, setStatus] = useState('');
  const channels = useQuery({ queryKey: channelsKey, queryFn: ({ signal }) => getChannels(signal), retry: false });
  const recent = useQuery<Poll[]>({ queryKey: sessionPollsKey, queryFn: async () => [], initialData: [], enabled: false });
  const directory = useQuery({ queryKey: ['poll-directory', channel], enabled: Boolean(channel), retry: false, staleTime: 15000,
    queryFn: ({ signal }) => discoverPolls(channel, id => cache.fetchQuery({ queryKey: ['poll', id],
      queryFn: ({ signal: pollSignal }) => getPoll(id, pollSignal), retry: false, staleTime: 30000 }), signal) });
  const items = mergePolls(recent.data ?? [], directory.data?.items ?? [], currentPoll ? [currentPoll] : [])
    .filter(poll => (!channel || poll.channelId === channel) && (!status || poll.status === status));
  return <section className={styles.directory} aria-labelledby="poll-directory-title">
    <h2 id="poll-directory-title">Buscar encuestas</h2>
    <div className={styles.directoryControls}>
      <label>Filtrar encuestas por canal<select aria-label="Filtrar encuestas por canal" value={channel} onChange={e => setChannel(e.target.value)} disabled={channels.isPending || channels.isError}>
        <option value="">Recientes de esta sesión</option>
        {channels.data?.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label>Estado de las encuestas<select aria-label="Estado de las encuestas" value={status} onChange={e => setStatus(e.target.value)}>
        <option value="">Todos</option>
        {Object.entries(states).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
      <label>Encuestas disponibles<select aria-label="Encuestas disponibles" value={items.some(item => item.pollId === currentPoll?.pollId) ? currentPoll!.pollId : ''}
        onChange={e => { if (e.target.value) navigate(`/polls/${encodeURIComponent(e.target.value)}`); }} disabled={!items.length}>
        <option value="">{items.length ? 'Selecciona una encuesta' : 'Sin encuestas disponibles'}</option>
        {items.map(item => <option key={item.pollId} value={item.pollId}>{item.question} — {states[item.status]}</option>)}
      </select></label>
      <Button disabled={!channel || directory.isFetching} onClick={() => {
        for (const item of items) void cache.invalidateQueries({ queryKey: ['poll', item.pollId], exact: true });
        void directory.refetch();
      }}>Actualizar encuestas</Button>
    </div>
    <p className={styles.hint}>{channel ? 'Encuestas referenciadas en los mensajes de este canal y recién creadas en esta sesión.' : 'Selecciona un canal para descubrir sus encuestas. Aquí aparecen las creadas o abiertas durante esta sesión.'}</p>
    {channels.isError && <><ErrorMessage message={readError(channels.error)} /><Button onClick={() => void channels.refetch()}>Reintentar canales</Button></>}
    {directory.isFetching && <LoadingIndicator />}
    {directory.isError && <><ErrorMessage message={readError(directory.error)} /><p className={styles.hint}>La consulta falló; no significa que el canal esté vacío. Puedes abrir una encuesta por ID.</p></>}
    {channel && directory.isSuccess && !directory.data.failures && !items.length && <EmptyState>No hay encuestas que coincidan con estos filtros en los mensajes del canal.</EmptyState>}
    {directory.data?.failures ? <p role="status">Algunas referencias no pudieron consultarse. Actualiza para reintentar.</p> : null}
    {directory.data?.truncated && <p className={styles.hint}>Se muestran hasta 25 referencias recientes del canal. Las demás siguen accesibles por ID.</p>}
  </section>;
}
