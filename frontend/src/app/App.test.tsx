import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, mount } from '../features/chat/testSupport';

describe('Rutas y compatibilidad compartidas', () => {
  it.each([
    ['/integrals', 'Calculadora e historial'], ['/integrals/i-1', 'Detalle de integral'],
    ['/polls/p-1', 'Encuesta'], ['/no-existe', 'Página no encontrada'],
  ])('conserva %s sin solicitudes de dominio de Andrés', (path, title) => {
    const { calls } = backend(); mount(path);
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.getByText('Pendiente de implementación')).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });
  it('permite navegar desde Chat a las herramientas y volver', async () => {
    const { calls } = backend(); mount('/channels');
    await userEvent.click(screen.getByRole('link', { name: /Integrales/ }));
    expect(screen.getByRole('heading', { name: 'Calculadora e historial' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Encuestas' }));
    expect(screen.getByRole('heading', { name: 'Encuesta' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Chat' }));
    expect(await screen.findByRole('heading', { name: 'Un canal para cada idea.' })).toBeInTheDocument();
    expect(calls.every(call => ['GetChannels'].includes(call.operation))).toBe(true);
  });
});
