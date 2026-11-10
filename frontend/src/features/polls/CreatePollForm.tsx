import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, ErrorMessage } from '../../components/ui';
import { useIdentity } from '../identity/IdentityProvider';
import { readError } from '../chat/errors';
import { createPoll, type CreatePollInput } from './api';
import styles from './Polls.module.css';

export function CreatePollForm() {
  const { user } = useIdentity();
  const [channel, setChannel] = useState('');
  const [question, setQuestion] = useState('');
  const [alternatives, setAlternatives] = useState('');
  const [duration, setDuration] = useState(5);
  const [validation, setValidation] = useState('');
  // A retry with an unchanged body must reuse the original key, even after a lost response.
  const attempt = useRef<{ body: string; key: string } | null>(null);
  const cache = useQueryClient();
  const creation = useMutation({ mutationFn: ({ input, key }: { input: CreatePollInput; key: string }) => createPoll(input, key),
    retry: false, onSuccess: poll => { cache.setQueryData(['poll', poll.pollId], poll); } });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!user || creation.isPending) return;
    const options = alternatives.split('\n').map(x => x.trim());
    if (!channel.trim() || !question.trim() || options.length < 2 || options.length > 10 ||
        options.some(x => !x) || new Set(options.map(x => x.toLocaleLowerCase())).size !== options.length ||
        !Number.isInteger(duration) || duration < 1 || duration > 1440) {
      setValidation('Indica canal y pregunta, entre 2 y 10 opciones distintas (una por línea) y duración de 1 a 1440 minutos.'); return;
    }
    setValidation('');
    const input = { channelId: channel.trim(), authorId: user.id, question: question.trim(), options, durationMinutes: duration };
    const body = JSON.stringify(input);
    if (!attempt.current || attempt.current.body !== body) attempt.current = { body, key: crypto.randomUUID() };
    creation.mutate({ input, key: attempt.current.key });
  }
  return <section><h2>Crear encuesta</h2>
    {!user && <p>Selecciona una identidad en <Link to="/">Inicio</Link> para crear una encuesta.</p>}
    <form className={styles.form} onSubmit={submit}>
      <label>ID del canal<input value={channel} onChange={e => setChannel(e.target.value)} required /></label>
      <label>Pregunta<input value={question} onChange={e => setQuestion(e.target.value)} required /></label>
      <label>Opciones, una por línea<textarea value={alternatives} onChange={e => setAlternatives(e.target.value)} required /></label>
      <label>Duración en minutos<input type="number" min={1} max={1440} step={1} value={duration} onChange={e => setDuration(Number(e.target.value))} required /></label>
      <Button type="submit" disabled={!user || creation.isPending}>{creation.isPending ? 'Creando…' : 'Crear encuesta'}</Button>
    </form>
    {validation && <ErrorMessage message={validation} />}
    {creation.isError && <><ErrorMessage message={readError(creation.error)} /><p>Se conserva la clave para reintentar esta misma encuesta sin duplicarla.</p></>}
    {creation.data && <p role="status" className={styles.link}>
      {creation.data.status === 'pending_announcement' ? 'Encuesta pendiente de publicación.' : creation.data.status === 'creation_failed' ? 'La encuesta no pudo publicarse.' : 'Encuesta registrada.'}
      {' '}<Link to={`/polls/${creation.data.pollId}`}>Abrir encuesta {creation.data.pollId}</Link>
    </p>}
  </section>;
}
