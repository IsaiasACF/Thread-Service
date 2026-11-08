import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount, savedIdentity } from './testSupport';

async function ready() { await screen.findByRole('article', { name: 'Mensaje m-1' }); await waitFor(() => expect(screen.getByLabelText('Nuevo mensaje')).toBeEnabled()); }
describe('Canales y conversación', () => {
  it('lista canales y navega entre ellos validando cada canal', async () => {
    const { calls } = backend(); mount('/channels');
    const channels = screen.getByRole('navigation', { name: 'Canales disponibles' });
    await userEvent.click(await within(channels).findByRole('link', { name: 'general' }));
    expect(await screen.findByRole('heading', { name: 'general' })).toBeInTheDocument();
    expect(within(channels).getByRole('link', { name: 'general' })).toHaveAttribute('aria-current', 'page');
    await userEvent.click(within(channels).getByRole('link', { name: 'proyecto' }));
    expect(await screen.findByText('Otro canal')).toBeInTheDocument();
    expect(screen.queryByText('Después')).not.toBeInTheDocument();
    expect(calls.filter(call => call.operation === 'GetChannel').map(call => call.variables.id)).toEqual(['c-1', 'c-2']);
  });
  it('crea un canal, actualiza el listado y lo abre', async () => {
    const { calls } = backend(); mount('/channels');
    await userEvent.click(screen.getByRole('button', { name: 'Crear canal' }));
    fireEvent.change(screen.getByLabelText('Nombre del canal'), { target: { value: 'ideas' } });
    await userEvent.click(screen.getByRole('button', { name: 'Crear y abrir' }));
    expect(await screen.findByRole('heading', { name: 'ideas' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'ideas' })).toHaveAttribute('aria-current', 'page');
    expect(calls.filter(call => call.operation === 'CreateChannel')).toHaveLength(1);
  });
  it('presenta el estado vacío de canales', async () => {
    backend({ GetChannels: () => json({ channels: [] }) }); mount('/channels');
    expect(await screen.findByText('Todavía no hay canales. Crea el primero.')).toBeInTheDocument();
  });
  it.each(['', 'x'.repeat(81)])('valida el nombre del canal antes del POST (caso %#)', async name => {
    const { calls } = backend(); mount('/channels');
    await userEvent.click(screen.getByRole('button', { name: 'Crear canal' }));
    fireEvent.change(screen.getByLabelText('Nombre del canal'), { target: { value: name } });
    await userEvent.click(screen.getByRole('button', { name: 'Crear y abrir' }));
    expect(await screen.findByText('El nombre debe tener entre 1 y 80 caracteres.')).toBeInTheDocument();
    expect(calls.some(call => call.operation === 'CreateChannel')).toBe(false);
  });
  it('no consulta mensajes de un canal inexistente', async () => {
    const { calls } = backend(); mount('/channels/missing');
    expect(await screen.findByRole('heading', { name: 'Canal no disponible' })).toBeInTheDocument();
    expect(calls.some(call => call.operation === 'GetMessages')).toBe(false);
  });
  it('muestra errores de conexión al listar canales', async () => {
    backend({ GetChannels: () => error('UPSTREAM_UNAVAILABLE') }); mount('/channels');
    expect(await screen.findByText(/No pudimos conectar/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar canales' })).toBeInTheDocument();
  });
  it('ordena cronológicamente, conserva saltos de línea y comparte consultas de autores', async () => {
    const { calls } = backend(); savedIdentity(); mount('/channels/c-1'); await ready();
    const articles = within(screen.getByLabelText('Mensajes del canal')).getAllByRole('article');
    expect(articles.map(item => item.getAttribute('aria-label'))).toEqual(['Mensaje m-1', 'Mensaje m-2']);
    expect(articles[0].textContent).toContain('Primero\nSegunda línea');
    await waitFor(() => expect(screen.getAllByText('Bruno').length).toBe(2));
    expect(calls.filter(call => call.operation === 'GetUser' && call.variables.id === 'u-2')).toHaveLength(1);
    expect(calls.some(call => call.operation === 'GetReplies')).toBe(false);
  });
  it('usa el ID del autor si su servicio falla sin romper mensajes', async () => {
    backend({ GetUser: call => call.variables.id === 'u-2' ? error('UPSTREAM_UNAVAILABLE') : json({ user: { id: 'u-1', displayName: 'Ana' } }) });
    savedIdentity(); mount('/channels/c-1'); await ready();
    expect(screen.getAllByTitle('u-2')).toHaveLength(2);
    expect(screen.getAllByText('u-2')).toHaveLength(2);
    expect(screen.getByLabelText('Nuevo mensaje')).toBeEnabled();
  });
  it('publica un mensaje, limpia el borrador y no duplica al actualizar', async () => {
    const { calls } = backend(); savedIdentity(); mount('/channels/c-1'); await ready();
    fireEvent.change(screen.getByLabelText('Nuevo mensaje'), { target: { value: 'Mi idea\nCon detalle' } });
    await userEvent.click(screen.getByRole('button', { name: /Enviar mensaje/ }));
    expect(await screen.findByText('Mensaje publicado.')).toBeInTheDocument();
    expect(screen.getByLabelText('Nuevo mensaje')).toHaveValue('');
    expect(await screen.findByRole('article', { name: 'Mensaje m-created' })).toHaveTextContent('Mi idea Con detalle');
    await waitFor(() => expect(screen.getByRole('button', { name: /↻ Actualizar mensajes/ })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: /↻ Actualizar mensajes/ }));
    await waitFor(() => expect(screen.getAllByRole('article', { name: 'Mensaje m-created' })).toHaveLength(1));
    expect(calls.filter(call => call.operation === 'SendMessage')).toHaveLength(1);
    expect(calls.find(call => call.operation === 'SendMessage')?.variables).toEqual({ channelId: 'c-1', authorId: 'u-1', content: 'Mi idea\nCon detalle' });
  });
  it.each(['', 'x'.repeat(4001)])('valida longitud del contenido sin POST (caso %#)', async content => {
    const { calls } = backend(); savedIdentity(); mount('/channels/c-1'); await ready();
    fireEvent.change(screen.getByLabelText('Nuevo mensaje'), { target: { value: content } });
    await userEvent.click(screen.getByRole('button', { name: /Enviar mensaje/ }));
    expect(await screen.findByText('El contenido debe tener entre 1 y 4000 caracteres.')).toBeInTheDocument();
    expect(calls.some(call => call.operation === 'SendMessage')).toBe(false);
  });
  it('conserva el borrador y advierte resultado incierto ante HTTP 200 con errores', async () => {
    const { calls } = backend({ SendMessage: () => error('UPSTREAM_TIMEOUT') }); savedIdentity(); mount('/channels/c-1'); await ready();
    fireEvent.change(screen.getByLabelText('Nuevo mensaje'), { target: { value: 'No perder este texto' } });
    await userEvent.click(screen.getByRole('button', { name: /Enviar mensaje/ }));
    expect(await screen.findByText(/El resultado es incierto/)).toBeInTheDocument();
    expect(screen.getByLabelText('Nuevo mensaje')).toHaveValue('No perder este texto');
    expect(screen.queryByText('Mensaje publicado.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Actualizar mensajes antes de repetir/ })).toBeInTheDocument();
    expect(calls.filter(call => call.operation === 'SendMessage')).toHaveLength(1);
    expect(screen.queryByText('private upstream detail')).not.toBeInTheDocument();
  });
  it('desactiva envíos durante el POST pendiente', async () => {
    let confirm!: (value: Response) => void;
    const { calls } = backend({ SendMessage: () => new Promise(resolve => { confirm = resolve; }) }); savedIdentity(); mount('/channels/c-1'); await ready();
    fireEvent.change(screen.getByLabelText('Nuevo mensaje'), { target: { value: 'Pendiente' } });
    await userEvent.click(screen.getByRole('button', { name: /Enviar mensaje/ }));
    expect(await screen.findByRole('button', { name: /Enviando/ })).toBeDisabled();
    expect(screen.getByLabelText('Nuevo mensaje')).toBeDisabled();
    expect(calls.filter(call => call.operation === 'SendMessage')).toHaveLength(1);
    confirm(error('UPSTREAM_UNAVAILABLE'));
    expect(await screen.findByText(/El resultado es incierto/)).toBeInTheDocument();
  });
  it('cancela la lectura obsoleta al cambiar de canal', async () => {
    let late!: (value: Response) => void;
    const { calls } = backend({ GetMessages: call => call.variables.channelId === 'c-1' ? new Promise(resolve => { late = resolve; }) : json({ messages: [{ id: 'other', channelId: 'c-2', authorId: 'u-1', content: 'Canal nuevo', createdAt: '2026-11-08T12:00:00Z' }] }) });
    mount('/channels/c-1');
    await waitFor(() => expect(calls.some(call => call.operation === 'GetMessages')).toBe(true));
    await userEvent.click(await screen.findByRole('link', { name: 'proyecto' }));
    expect(await screen.findByText('Canal nuevo')).toBeInTheDocument();
    expect(calls.find(call => call.operation === 'GetMessages' && call.variables.channelId === 'c-1')?.signal?.aborted).toBe(true);
    late(json({ messages: [{ id: 'old', content: 'Contenido obsoleto', channelId: 'c-1', authorId: 'u-1', createdAt: '2026-11-08T11:00:00Z' }] }));
    expect(screen.queryByText('Contenido obsoleto')).not.toBeInTheDocument();
  });
});

it('no habilita escrituras solo porque hay un ID en localStorage', async () => {
  let validate!: (response: Response) => void;
  backend({ GetUser: call => call.variables.id === 'u-1' ? new Promise(resolve => { validate = resolve; }) : json({ user: null }) });
  savedIdentity(); mount('/channels/c-1');
  await screen.findByRole('article', { name: 'Mensaje m-1' });
  expect(screen.getByLabelText('Nuevo mensaje')).toBeDisabled();
  validate(json({ user: { id: 'u-1', displayName: 'Ana' } }));
  await waitFor(() => expect(screen.getByLabelText('Nuevo mensaje')).toBeEnabled());
});

it('no solapa lecturas aunque una consulta dure más que el intervalo', async () => {
  const { calls } = backend({ GetMessages: () => new Promise(() => {}) });
  const view = mount('/channels/c-1');
  await waitFor(() => expect(calls.some(call => call.operation === 'GetMessages')).toBe(true));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 5250)); });
  expect(calls.filter(call => call.operation === 'GetMessages')).toHaveLength(1);
  view.unmount();
  expect(calls.find(call => call.operation === 'GetMessages')?.signal?.aborted).toBe(true);
}, 12_000);

it('retira la conversación si el canal deja de estar disponible', async () => {
  let available = true;
  backend({ GetChannel: () => json({ channel: available ? { id: 'c-1', name: 'general' } : null }) });
  const { cache } = mount('/channels/c-1');
  await screen.findByRole('article', { name: 'Mensaje m-1' });
  available = false;
  await act(async () => { await cache.invalidateQueries({ queryKey: ['channel', 'c-1'] }); });
  expect(await screen.findByRole('heading', { name: 'Canal no disponible' })).toBeInTheDocument();
  expect(screen.queryByLabelText('Nuevo mensaje')).not.toBeInTheDocument();
});

it('una creación tardía de canal no abandona la pantalla de Andrés', async () => {
  let finish!: (response: Response) => void;
  backend({ CreateChannel: () => new Promise(resolve => { finish = resolve; }) }); mount('/channels');
  await userEvent.click(screen.getByRole('button', { name: 'Crear canal' }));
  fireEvent.change(screen.getByLabelText('Nombre del canal'), { target: { value: 'tardío' } });
  await userEvent.click(screen.getByRole('button', { name: 'Crear y abrir' }));
  await screen.findByRole('button', { name: 'Creando…' });
  await userEvent.click(screen.getByRole('link', { name: /Integrales/ }));
  await screen.findByRole('heading', { name: 'Calculadora e historial' });
  await act(async () => { finish(json({ createChannel: { id: 'c-late', name: 'tardío' } })); });
  expect(screen.getByRole('heading', { name: 'Calculadora e historial' })).toBeInTheDocument();
});

it('permite 4000 caracteres Unicode sin aplicar un límite UTF-16 más estricto', async () => {
  const { calls } = backend(); savedIdentity(); mount('/channels/c-1'); await ready();
  const content = '😀'.repeat(4000);
  fireEvent.change(screen.getByLabelText('Nuevo mensaje'), { target: { value: content } });
  await userEvent.click(screen.getByRole('button', { name: /Enviar mensaje/ }));
  expect(await screen.findByText('Mensaje publicado.')).toBeInTheDocument();
  expect(calls.find(call => call.operation === 'SendMessage')?.variables.content).toBe(content);
});
