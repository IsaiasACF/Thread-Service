import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, json, mount, savedIdentity } from '../features/chat/testSupport';

describe('Interacciones de navegación y herramientas', () => {
  it('filtra canales existentes y recupera la lista al limpiar la búsqueda', async () => {
    backend(); mount('/channels');
    await screen.findByRole('link', { name: 'general' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Buscar canales' }), 'proy');
    expect(screen.getByRole('link', { name: 'proyecto' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'general' })).not.toBeInTheDocument();
    await userEvent.clear(screen.getByRole('searchbox', { name: 'Buscar canales' }));
    expect(screen.getByRole('link', { name: 'general' })).toBeInTheDocument();
  });
  it('muestra ausencia de coincidencias sin confundirla con ausencia de canales', async () => {
    backend(); mount('/channels');
    await screen.findByRole('link', { name: 'general' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Buscar canales' }), 'inexistente');
    expect(screen.getByText('No hay canales que coincidan.')).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay canales/)).not.toBeInTheDocument();
  });
  it('rellena un ejemplo editable sin iniciar automáticamente un cálculo', async () => {
    const { calls } = backend({ IntegralHistory: () => json({ integrals: { items: [], total: 0, limit: 20, offset: 0 } }) });
    mount('/integrals');
    await userEvent.click(screen.getByRole('button', { name: 'Integral definida' }));
    expect(screen.getByLabelText('Integral en LaTeX')).toHaveValue('\\int_0^1 x^2 \\, dx');
    expect(screen.getByLabelText('Integral en LaTeX')).toHaveFocus();
    expect(calls.filter(call => call.operation === 'CalculateIntegral')).toHaveLength(0);
    await userEvent.type(screen.getByLabelText('Integral en LaTeX'), ' ');
    expect(screen.getByRole('button', { name: 'Integral definida' })).toHaveAttribute('aria-pressed', 'false');
  });
  it('confirma la copia únicamente después de escribir al portapapeles', async () => {
    const user = userEvent.setup();
    backend(); savedIdentity(); mount('/');
    const button = await screen.findByRole('button', { name: 'Copiar ID de usuario' });
    await user.click(button);
    await waitFor(() => expect(screen.getByText('Copiado al portapapeles.')).toBeInTheDocument());
    expect(await navigator.clipboard.readText()).toBe('u-1');
  });
});
