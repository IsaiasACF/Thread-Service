import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount, savedIdentity } from '../chat/testSupport';
import { IDENTITY_STORAGE_KEY } from './IdentityProvider';

async function fill(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
describe('Identidad local verificada', () => {
  it('crea un usuario y guarda solo su ID después de confirmar', async () => {
    const { calls } = backend(); mount();
    await fill('Tu nombre', 'Camila');
    await userEvent.click(screen.getByRole('button', { name: 'Crear identidad' }));
    expect(await screen.findByText('Hola, Camila')).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(IDENTITY_STORAGE_KEY)!)).toEqual({ id: 'u-created' });
    expect(calls.find(call => call.operation === 'CreateUser')?.variables).toEqual({ name: 'Camila' });
  });
  it('valida un ID existente y permite cambiar de identidad', async () => {
    backend(); savedIdentity(); mount();
    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument();
    await fill('ID de usuario', 'u-2');
    await userEvent.click(screen.getByRole('button', { name: 'Usar este ID' }));
    expect(await screen.findByText('Hola, Bruno')).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(IDENTITY_STORAGE_KEY)!)).toEqual({ id: 'u-2' });
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar identidad local' }));
    expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText('Hola, Bruno')).not.toBeInTheDocument();
  });
  it('no acepta un ID desconocido', async () => {
    backend(); mount(); await fill('ID de usuario', 'missing');
    await userEvent.click(screen.getByRole('button', { name: 'Usar este ID' }));
    expect(await screen.findByText('No encontramos esa identidad.')).toBeInTheDocument();
    expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull();
  });
  it('recupera la identidad almacenada consultando al Gateway', async () => {
    const { calls } = backend(); savedIdentity(); mount();
    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument();
    expect(calls.filter(call => call.operation === 'GetUser' && call.variables.id === 'u-1')).toHaveLength(1);
  });
  it('descarta una identidad almacenada inexistente', async () => {
    backend(); savedIdentity('missing'); mount();
    expect((await screen.findAllByText('La identidad guardada no existe. Selecciona otra identidad.')).length).toBeGreaterThan(0);
    await waitFor(() => expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull());
    expect(screen.queryByRole('region', { name: 'Identidad seleccionada' })).not.toBeInTheDocument();
  });
  it('conserva el ID ante una falla temporal y permite revalidarlo', async () => {
    let available = false;
    backend({ GetUser: () => available ? json({ user: { id: 'u-1', displayName: 'Ana' } }) : error('UPSTREAM_UNAVAILABLE', 'users') });
    savedIdentity(); mount();
    expect((await screen.findAllByText(/No pudimos conectar/)).length).toBeGreaterThan(0);
    expect(JSON.parse(localStorage.getItem(IDENTITY_STORAGE_KEY)!)).toEqual({ id: 'u-1' });
    expect(screen.queryByText('Hola, Ana')).not.toBeInTheDocument();
    available = true;
    await userEvent.click(screen.getByRole('button', { name: 'Revalidar identidad' }));
    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument();
  });
  it.each(['', 'x'.repeat(81)])('valida nombre sin hacer POST (%s)', async name => {
    const { calls } = backend(); mount(); await fill('Tu nombre', name);
    await userEvent.click(screen.getByRole('button', { name: 'Crear identidad' }));
    expect(await screen.findByText('El nombre debe tener entre 1 y 80 caracteres.')).toBeInTheDocument();
    expect(calls.some(call => call.operation === 'CreateUser')).toBe(false);
  });
  it('no confía en el nombre almacenado como autenticación', async () => {
    backend(); localStorage.setItem(IDENTITY_STORAGE_KEY, JSON.stringify({ id: 'u-1', displayName: 'Nombre falso' })); mount();
    expect(await screen.findByText('Hola, Ana')).toBeInTheDocument();
    expect(screen.queryByText('Nombre falso')).not.toBeInTheDocument();
  });
});

it('conserva el nombre ante creación incierta y no selecciona identidad sin confirmación', async () => {
  const { calls } = backend({ CreateUser: () => error('UPSTREAM_TIMEOUT', 'users') }); mount();
  fireEvent.change(screen.getByLabelText('Tu nombre'), { target: { value: 'Nombre conservado' } });
  await userEvent.click(screen.getByRole('button', { name: 'Crear identidad' }));
  expect(await screen.findByText(/No pudimos confirmar la creación/)).toBeInTheDocument();
  expect(screen.getByLabelText('Tu nombre')).toHaveValue('Nombre conservado');
  expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull();
  expect(calls.filter(call => call.operation === 'CreateUser')).toHaveLength(1);
});

it('rechaza también una identidad almacenada con error NOT_FOUND', async () => {
  backend({ GetUser: () => error('NOT_FOUND', 'users') }); savedIdentity(); mount();
  expect((await screen.findAllByText('La identidad guardada no existe. Selecciona otra identidad.')).length).toBeGreaterThan(0);
  await waitFor(() => expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull());
});

it('una creación tardía no reactiva una identidad cerrada', async () => {
  let finish!: (response: Response) => void;
  backend({ CreateUser: () => new Promise(resolve => { finish = resolve; }) }); savedIdentity(); mount();
  await screen.findByText('Hola, Ana');
  fireEvent.change(screen.getByLabelText('Tu nombre'), { target: { value: 'Identidad nueva' } });
  await userEvent.click(screen.getByRole('button', { name: 'Crear identidad' }));
  await screen.findByRole('button', { name: 'Creando identidad…' });
  await userEvent.click(screen.getByRole('button', { name: 'Cerrar identidad local' }));
  finish(json({ createUser: { id: 'u-late', displayName: 'Identidad nueva' } }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Crear identidad' })).toBeEnabled());
  expect(localStorage.getItem(IDENTITY_STORAGE_KEY)).toBeNull();
  expect(screen.queryByText('Hola, Identidad nueva')).not.toBeInTheDocument();
});

it('cuenta 80 caracteres Unicode igual que el contrato del Gateway', async () => {
  const { calls } = backend(); mount();
  const name = '😀'.repeat(80);
  fireEvent.change(screen.getByLabelText('Tu nombre'), { target: { value: name } });
  await userEvent.click(screen.getByRole('button', { name: 'Crear identidad' }));
  expect(await screen.findByText(`Hola, ${name}`)).toBeInTheDocument();
  expect(calls.find(call => call.operation === 'CreateUser')?.variables.name).toBe(name);
});
