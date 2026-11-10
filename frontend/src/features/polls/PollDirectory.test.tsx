import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount, savedIdentity } from '../chat/testSupport';

const id = '123e4567-e89b-12d3-a456-426614174000';
const foreignId = '123e4567-e89b-12d3-a456-426614174001';
const poll = { pollId: id, channelId: 'c-1', authorId: 'u-1', question: 'Reunión del equipo',
  options: [{ optionId: 'o-1', position: 0, text: 'Sí', voteCount: 0 }, { optionId: 'o-2', position: 1, text: 'No', voteCount: 0 }],
  status: 'open', durationMinutes: 5, closesAt: '2026-11-10T12:05:00Z', createdAt: '2026-11-10T12:00:00Z', closedAt: null, totalVotes: 0, creationError: null };
const message = (pollId: string, n: number) => ({ id: `m-${n}`, channelId: 'c-1', authorId: 'u-1',
  content: `📊 Nueva encuesta: Título del anuncio\nPoll ID: ${pollId}\nAlternativas:\n- Sí\n- No`, createdAt: '2026-11-10T12:00:00Z' });

describe('Directorio y creación de encuestas', () => {
  it('descubre por canal, deduplica y verifica título y pertenencia mediante Polls', async () => {
    const { calls } = backend({ GetMessages: () => json({ messages: [message(id, 1), message(id, 2), message(foreignId, 3)] }),
      PollDetail: call => json({ poll: call.variables.id === id ? poll : { ...poll, pollId: foreignId, channelId: 'c-2', question: 'Otro canal' } }) });
    mount('/polls/pendiente');
    await userEvent.selectOptions(await screen.findByLabelText('Filtrar encuestas por canal'), 'c-1');
    const menu = screen.getByLabelText('Encuestas disponibles');
    await within(menu).findByRole('option', { name: 'Reunión del equipo — Abierta' });
    expect(within(menu).queryByRole('option', { name: /Otro canal/ })).not.toBeInTheDocument();
    expect(within(menu).queryByRole('option', { name: /Título del anuncio/ })).not.toBeInTheDocument();
    expect(calls.filter(call => call.operation === 'PollDetail' && call.variables.id === id)).toHaveLength(1);
    await userEvent.selectOptions(menu, id);
    expect(await screen.findByRole('heading', { name: 'Reunión del equipo' })).toBeInTheDocument();
  });
  it('filtra por estado sin modificar los datos de la encuesta', async () => {
    backend({ GetMessages: () => json({ messages: [message(id, 1)] }), PollDetail: () => json({ poll }) });
    mount('/polls/pendiente?channel=c-1');
    const menu = screen.getByLabelText('Encuestas disponibles');
    await within(menu).findByRole('option', { name: /Reunión del equipo/ });
    await userEvent.selectOptions(screen.getByLabelText('Estado de las encuestas'), 'closed');
    expect(menu).toBeDisabled();
    expect(within(menu).queryByRole('option', { name: /Reunión del equipo/ })).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Estado de las encuestas'), 'open');
    expect(within(menu).getByRole('option', { name: /Reunión del equipo/ })).toBeInTheDocument();
  });
  it('diferencia una caída de Messages de un listado vacío', async () => {
    backend({ GetMessages: () => error('UPSTREAM_UNAVAILABLE', 'messages') });
    mount('/polls/pendiente?channel=c-1');
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/La consulta falló/)).toBeInTheDocument();
    expect(screen.queryByText(/No hay encuestas que coincidan/)).not.toBeInTheDocument();
  });
  it('selecciona el canal por nombre al crear y muestra la encuesta pendiente en la sesión', async () => {
    savedIdentity();
    const { calls } = backend({ CreatePoll: () => json({ createPoll: { ...poll, status: 'pending_announcement' } }) });
    mount('/polls/pendiente');
    const canal = screen.getByLabelText('Canal para la encuesta');
    await waitFor(() => expect(canal).toBeEnabled());
    await userEvent.selectOptions(canal, 'c-1');
    await userEvent.type(screen.getByLabelText('Pregunta'), poll.question);
    await userEvent.type(screen.getByLabelText('Opciones, una por línea'), 'Sí\nNo');
    await userEvent.click(screen.getByRole('button', { name: 'Crear encuesta' }));
    await within(screen.getByLabelText('Encuestas disponibles')).findByRole('option', { name: 'Reunión del equipo — Pendiente' });
    const creation = calls.find(call => call.operation === 'CreatePoll');
    expect((creation?.variables as unknown as { input: { channelId: string } }).input.channelId).toBe('c-1');
  });
  it('conserva el canal de contexto al abrir encuestas desde el chat', async () => {
    backend(); mount('/channels/c-1');
    await screen.findByRole('heading', { name: 'general' });
    await userEvent.click(screen.getByRole('link', { name: 'Encuestas' }));
    expect(screen.getByLabelText('Filtrar encuestas por canal')).toHaveValue('c-1');
    expect(screen.getByLabelText('Canal para la encuesta')).toHaveValue('c-1');
  });
});
