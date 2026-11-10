import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { Icon } from '../../components/Icon';
import { CopyButton } from '../../components/CopyButton';
import { useIdentity } from '../identity/IdentityProvider';
import { readError } from '../chat/errors';
import { closePoll, getPoll, votePoll } from './api';
import { CreatePollForm } from './CreatePollForm';
import styles from './Polls.module.css';

const statuses = { pending_announcement: 'Pendiente de publicación', open: 'Abierta', closed: 'Cerrada', creation_failed: 'No se pudo publicar' };

export default function PollPage() {
  const { pollId } = useParams();
  const navigate = useNavigate();
  const [id, setId] = useState('');
  const [selected, setSelected] = useState('');
  const { user } = useIdentity();
  const cache = useQueryClient();
  const hasPoll = Boolean(pollId && pollId !== 'pendiente');
  const detail = useQuery({ queryKey: ['poll', pollId], enabled: hasPoll, retry: false,
    queryFn: ({ signal }) => getPoll(pollId!, signal),
    refetchInterval: query => ['open', 'pending_announcement'].includes(query.state.data?.status ?? '') ? 5000 : false,
    refetchIntervalInBackground: false });
  const refresh = () => { void cache.invalidateQueries({ queryKey: ['poll', pollId] }); };
  const vote = useMutation({ mutationFn: (optionId: string) => votePoll(pollId!, user!.id, optionId), retry: false, onSettled: refresh });
  const close = useMutation({ mutationFn: () => closePoll(pollId!, user!.id), retry: false,
    onSuccess: poll => cache.setQueryData(['poll', poll.pollId], poll), onSettled: refresh });
  const resetVote = vote.reset;
  const resetClose = close.reset;
  useEffect(() => { setSelected(''); resetVote(); resetClose(); }, [pollId, user?.id, resetVote, resetClose]);
  const poll = detail.data;
  function open(event: FormEvent) { event.preventDefault(); if (id.trim()) navigate(`/polls/${encodeURIComponent(id.trim())}`); }
  const busy = vote.isPending || close.isPending;
  return <section className={styles.page}><div className={styles.heading}><span className={styles.headingIcon}><Icon name="poll" /></span><h1>Encuesta</h1></div>
    <form onSubmit={open} className={styles.form}>
      <label>ID de encuesta<input value={id} onChange={e => setId(e.target.value)} required /></label>
      <Button type="submit">Abrir encuesta</Button>
    </form>
    {hasPoll && detail.isPending && <LoadingIndicator />}
    {detail.isError && <><ErrorMessage message={readError(detail.error)} /><Button onClick={() => void detail.refetch()}>Reintentar consulta</Button></>}
    {detail.isSuccess && !poll && <EmptyState>La encuesta no existe.</EmptyState>}
    {poll && <article className={styles.card}>
      <h2>{poll.question}</h2><p role="status">{statuses[poll.status]}</p>
      <p>Cierre: {new Date(poll.closesAt).toLocaleString('es-CL')} · {poll.totalVotes} votos</p>
      <p className={styles.link}>Enlace: <Link to={`/polls/${poll.pollId}`}>{`${window.location.origin}/polls/${poll.pollId}`}</Link></p>
      <CopyButton value={`${window.location.origin}/polls/${poll.pollId}`} label="Copiar enlace de encuesta" />
      {poll.creationError && <p>{poll.creationError}</p>}
      {!user && <p>Selecciona una identidad en <Link to="/">Inicio</Link> para votar o cerrar.</p>}
      <fieldset disabled={poll.status !== 'open' || !user || busy || vote.isSuccess}>
        <legend>Alternativas</legend>
        {[...poll.options].sort((a,b) => a.position - b.position).map(option => <label className={styles.option} key={option.optionId}>
          <input type="radio" name={`option-${poll.pollId}`} value={option.optionId} checked={selected === option.optionId} onChange={() => setSelected(option.optionId)} />
          <span>{option.text}</span><strong>{option.voteCount} votos · {poll.totalVotes ? Math.round(option.voteCount / poll.totalVotes * 100) : 0}%</strong>
          <meter min={0} max={Math.max(1, poll.totalVotes)} value={option.voteCount} aria-label={`Votos de ${option.text}`} />
        </label>)}
      </fieldset>
      <div className={styles.toolbar}>
        <Button disabled={!selected || !user || busy || poll.status !== 'open' || vote.isSuccess} onClick={() => vote.mutate(selected)}>Votar</Button>
        {user?.id === poll.authorId && poll.status === 'open' && <Button disabled={busy} onClick={() => close.mutate()}>Cerrar encuesta</Button>}
        <Button disabled={detail.isFetching} onClick={() => void detail.refetch()}>Actualizar resultados</Button>
      </div>
      {vote.isSuccess && <p role="status">Voto registrado.</p>}
      {(vote.isError || close.isError) && <ErrorMessage message={readError(vote.error ?? close.error)} />}
    </article>}
    <CreatePollForm />
  </section>;
}
