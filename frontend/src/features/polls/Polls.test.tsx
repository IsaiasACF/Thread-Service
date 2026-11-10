import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount, savedIdentity } from '../chat/testSupport';

const poll = { pollId: 'p-1', channelId: 'c-1', authorId: 'u-1', question: '¿Qué elegimos?',
  options: [{ optionId: 'option-a', position: 0, text: 'A', voteCount: 0 }, { optionId: 'option-b', position: 1, text: 'B', voteCount: 0 }],
  status: 'open', durationMinutes: 5, closesAt: '2026-11-09T12:05:00Z', createdAt: '2026-11-09T12:00:00Z',
  closedAt: null, totalVotes: 0, creationError: null };
describe('Encuestas mediante Gateway', () => {
  it('usa optionId al votar y refresca resultados', async () => {
    savedIdentity();
    const { calls } = backend({ PollDetail: () => json({ poll }), VotePoll: () => json({ votePoll: { pollId: 'p-1', voterId: 'u-1', optionId: 'option-b', castAt: poll.createdAt } }) });
    mount('/polls/p-1');
    await waitFor(() => expect(screen.getByRole('radio', { name: /B/ })).toBeEnabled());
    await userEvent.click(screen.getByRole('radio', { name: /B/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Votar' }));
    expect(await screen.findByText('Voto registrado.')).toBeInTheDocument();
    expect(calls.find(c => c.operation === 'VotePoll')?.variables.optionId).toBe('option-b');
    expect(calls.filter(c => c.operation === 'VotePoll')).toHaveLength(1);
  });
  it('deshabilita votar cuando está pendiente', async () => {
    savedIdentity(); backend({ PollDetail: () => json({ poll: { ...poll, status: 'pending_announcement' } }) });
    mount('/polls/p-1');
    expect(await screen.findByText('Pendiente de publicación')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Votar' })).toBeDisabled();
  });
  it('cierra como autor y muestra estado cerrado', async () => {
    savedIdentity();
    const { calls } = backend({ PollDetail: () => json({ poll }), ClosePoll: () => json({ closePoll: { ...poll, status: 'closed' } }) });
    mount('/polls/p-1');
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar encuesta' }));
    await waitFor(() => expect(calls.filter(c => c.operation === 'ClosePoll')).toHaveLength(1));
    expect(calls.find(c => c.operation === 'ClosePoll')?.variables.authorId).toBe('u-1');
  });
  it('no ofrece cierre a otro usuario', async () => {
    savedIdentity('u-2'); backend({ PollDetail: () => json({ poll }) }); mount('/polls/p-1');
    await screen.findByText(poll.question);
    expect(screen.queryByRole('button', { name: 'Cerrar encuesta' })).not.toBeInTheDocument();
  });
  it('reutiliza clave de idempotencia después de una respuesta perdida', async () => {
    savedIdentity(); const { calls } = backend({ CreatePoll: () => error('UPSTREAM_TIMEOUT', 'polls') });
    mount('/polls/pendiente');
    await userEvent.type(screen.getByLabelText('ID del canal'), 'c-1');
    await userEvent.type(screen.getByLabelText('Pregunta'), 'Q');
    await userEvent.type(screen.getByLabelText('Opciones, una por línea'), 'A\nB');
    const submit = screen.getByRole('button', { name: 'Crear encuesta' });
    await waitFor(() => expect(submit).toBeEnabled());
    await userEvent.click(submit); await screen.findByRole('alert');
    await userEvent.click(submit);
    await waitFor(() => expect(calls.filter(c => c.operation === 'CreatePoll')).toHaveLength(2));
    const creations = calls.filter(c => c.operation === 'CreatePoll');
    expect(creations[0].variables.idempotencyKey).toBeTruthy();
    expect(creations[0].variables.idempotencyKey).toBe(creations[1].variables.idempotencyKey);
    expect(calls.some(c => c.operation === 'PollDetail')).toBe(false);
  });
});
