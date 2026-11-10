import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, json, mount } from '../features/chat/testSupport';

describe('Rutas y compatibilidad compartidas', () => {
  it.each([
    ['/integrals', 'Calculadora e historial'], ['/integrals/i-1', 'Detalle de integral'],
    ['/polls/p-1', 'Encuesta'], ['/no-existe', 'Página no encontrada'],
  ])('conserva la ruta %s', (path, title) => {
    backend({ IntegralHistory: () => json({ integrals: { items: [], total: 0, limit: 20, offset: 0 } }),
      IntegralDetail: () => json({ integral: null }), PollDetail: () => json({ poll: null }) }); mount(path);
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
  });
  it('permite navegar desde Chat a las herramientas y volver', async () => {
    const { calls } = backend({ IntegralHistory: () => json({ integrals: { items: [], total: 0, limit: 20, offset: 0 } }) }); mount('/channels');
    await userEvent.click(screen.getByRole('link', { name: /Integrales/ }));
    expect(screen.getByRole('heading', { name: 'Calculadora e historial' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Encuestas' }));
    expect(screen.getByRole('heading', { name: 'Encuesta' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Chat' }));
    expect(await screen.findByRole('heading', { name: 'Selecciona un canal' })).toBeInTheDocument();
    expect(calls.every(call => ['GetChannels', 'IntegralHistory'].includes(call.operation))).toBe(true);
  });
});
