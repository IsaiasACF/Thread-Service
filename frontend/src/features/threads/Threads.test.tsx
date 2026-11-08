import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount, savedIdentity } from '../chat/testSupport';

async function openFirst() {
  const root = await screen.findByRole('article', { name: 'Mensaje m-1' });
  await userEvent.click(within(root).getByRole('button', { name: /Ver respuestas/ }));
  return screen.findByRole('dialog', { name: 'Respuestas del mensaje' });
}
describe('Threads de un solo nivel', () => {
  it('solo consulta el mensaje seleccionado y muestra thread vacío', async () => {
    const { calls } = backend(); savedIdentity(); mount('/channels/c-1');
    await screen.findByRole('article', { name: 'Mensaje m-1' });
    expect(calls.some(call => call.operation === 'GetReplies')).toBe(false);
    const panel = await openFirst();
    expect(await within(panel).findByText(/Aún no hay respuestas/)).toBeInTheDocument();
    expect(within(panel).getByRole('article', { name: 'Mensaje m-1' })).toBeInTheDocument();
    expect(calls.filter(call => call.operation === 'GetReplies').map(call => call.variables)).toEqual([{ channelId: 'c-1', messageId: 'm-1' }]);
    expect(within(panel).queryByRole('button', { name: /Ver respuestas/ })).not.toBeInTheDocument();
  });
  it('publica respuesta confirmada y la conserva tras refrescar', async () => {
    const { calls } = backend(); savedIdentity(); mount('/channels/c-1');
    const panel = await openFirst();
    await waitFor(() => expect(within(panel).getByLabelText('Tu respuesta')).toBeEnabled());
    fireEvent.change(within(panel).getByLabelText('Tu respuesta'), { target: { value: 'Respuesta persistida por la API simulada' } });
    await userEvent.click(within(panel).getByRole('button', { name: /Publicar respuesta/ }));
    expect(await within(panel).findByText('Respuesta publicada.')).toBeInTheDocument();
    expect(await within(panel).findByRole('article', { name: 'Mensaje r-created' })).toHaveTextContent('Respuesta persistida por la API simulada');
    await waitFor(() => expect(within(panel).getByRole('button', { name: 'Actualizar respuestas' })).toBeEnabled());
    await userEvent.click(within(panel).getByRole('button', { name: 'Actualizar respuestas' }));
    await waitFor(() => expect(within(panel).getAllByRole('article', { name: 'Mensaje r-created' })).toHaveLength(1));
    expect(within(panel).getByLabelText('Tu respuesta')).toHaveValue('');
    expect(calls.find(call => call.operation === 'CreateReply')?.variables).toEqual({ channelId: 'c-1', messageId: 'm-1', authorId: 'u-1', content: 'Respuesta persistida por la API simulada' });
    expect(calls.some(call => call.operation === 'SendMessage')).toBe(false);
  });
  it('muestra error de mensaje raíz inexistente y bloquea respuesta', async () => {
    backend({ GetReplies: () => error('NOT_FOUND', 'threads') }); savedIdentity(); mount('/channels/c-1'); const panel = await openFirst();
    expect(await within(panel).findByText('El mensaje original ya no está disponible.')).toBeInTheDocument();
    expect(within(panel).getByLabelText('Tu respuesta')).toBeDisabled();
  });
  it('conserva la respuesta ante un fallo ambiguo sin reintentar POST', async () => {
    const { calls } = backend({ CreateReply: () => error('UPSTREAM_TIMEOUT', 'threads') }); savedIdentity(); mount('/channels/c-1'); const panel = await openFirst();
    await waitFor(() => expect(within(panel).getByLabelText('Tu respuesta')).toBeEnabled());
    fireEvent.change(within(panel).getByLabelText('Tu respuesta'), { target: { value: 'Mi borrador' } });
    await userEvent.click(within(panel).getByRole('button', { name: /Publicar respuesta/ }));
    expect(await within(panel).findByText(/El resultado es incierto/)).toBeInTheDocument();
    expect(within(panel).getByLabelText('Tu respuesta')).toHaveValue('Mi borrador');
    expect(calls.filter(call => call.operation === 'CreateReply')).toHaveLength(1);
  });
  it('ordena respuestas y no permite respuestas anidadas', async () => {
    backend({ GetReplies: () => json({ replies: [
      { id: 'r-2', channelId: 'c-1', messageId: 'm-1', authorId: 'u-1', content: 'Respuesta posterior', createdAt: '2026-11-08T15:00:00Z' },
      { id: 'r-1', channelId: 'c-1', messageId: 'm-1', authorId: 'u-1', content: 'Respuesta anterior', createdAt: '2026-11-08T14:00:00Z' },
    ] }) }); mount('/channels/c-1'); const panel = await openFirst();
    await within(panel).findByText('Respuesta posterior');
    expect(within(panel).getAllByRole('article').map(item => item.getAttribute('aria-label'))).toEqual(['Mensaje m-1', 'Mensaje r-1', 'Mensaje r-2']);
    expect(within(panel).queryByRole('button', { name: /Ver respuestas/ })).not.toBeInTheDocument();
  });
  it('cancela consultas y devuelve el foco al cerrar con Escape', async () => {
    const { calls } = backend({ GetReplies: () => new Promise(() => {}) }); mount('/channels/c-1');
    const original = await screen.findByRole('article', { name: 'Mensaje m-1' });
    const trigger = within(original).getByRole('button', { name: /Ver respuestas/ });
    await userEvent.click(trigger);
    await screen.findByRole('dialog');
    await waitFor(() => expect(calls.some(call => call.operation === 'GetReplies')).toBe(true));
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(calls.find(call => call.operation === 'GetReplies')?.signal?.aborted).toBe(true);
  });
  it('consulta otro mensaje y cierra el panel al cambiar de canal', async () => {
    const { calls } = backend(); mount('/channels/c-1'); await openFirst();
    const other = screen.getByRole('article', { name: 'Mensaje m-2' });
    await userEvent.click(within(other).getByRole('button', { name: /Ver respuestas/ }));
    await waitFor(() => expect(calls.filter(call => call.operation === 'GetReplies').map(call => call.variables.messageId)).toEqual(['m-1', 'm-2']));
    await userEvent.click(screen.getByRole('link', { name: 'proyecto' }));
    expect(await screen.findByText('Otro canal')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('refresca mensajes e hilo activo y deja de consultar el hilo cerrado', async () => {
    const { calls } = backend(); mount('/channels/c-1'); const panel = await openFirst();
    await within(panel).findByText(/Aún no hay respuestas/);
    const initialMessages = calls.filter(call => call.operation === 'GetMessages').length;
    const initialReplies = calls.filter(call => call.operation === 'GetReplies').length;
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 5250)); });
    expect(calls.filter(call => call.operation === 'GetMessages').length).toBeGreaterThan(initialMessages);
    expect(calls.filter(call => call.operation === 'GetReplies').length).toBeGreaterThan(initialReplies);
    await userEvent.click(within(panel).getByRole('button', { name: 'Cerrar respuestas' }));
    const closedCount = calls.filter(call => call.operation === 'GetReplies').length;
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 5250)); });
    expect(calls.filter(call => call.operation === 'GetReplies')).toHaveLength(closedCount);
  }, 20_000);
});

it.each(['   ', 'x'.repeat(4001)])('valida contenido de respuesta sin POST (caso %#)', async content => {
  const { calls } = backend(); savedIdentity(); mount('/channels/c-1');
  const panel = await openFirst();
  await waitFor(() => expect(within(panel).getByLabelText('Tu respuesta')).toBeEnabled());
  fireEvent.change(within(panel).getByLabelText('Tu respuesta'), { target: { value: content } });
  await userEvent.click(within(panel).getByRole('button', { name: /Publicar respuesta/ }));
  expect(await within(panel).findByText('El contenido debe tener entre 1 y 4000 caracteres.')).toBeInTheDocument();
  expect(calls.some(call => call.operation === 'CreateReply')).toBe(false);
});
