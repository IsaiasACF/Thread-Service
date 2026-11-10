import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, error, json, mount } from '../chat/testSupport';

const integral = { id: 'i-1', latex: 'integral', status: 'calculated', durationMs: 3,
  createdAt: '2026-11-09T12:00:00Z', result: { latex: 'x^2/2', numeric: null, indefinite: true },
  error: null, source: { kind: 'rest', channelId: null, authorId: null, messageId: null } };
const page = { items: [], total: 0, limit: 20, offset: 0 };
describe('Integrales mediante Gateway', () => {
  it('calcula y muestra resultado e invalida historial sin reintentar la escritura', async () => {
    const { calls } = backend({ IntegralHistory: () => json({ integrals: page }), CalculateIntegral: () => json({ calculateIntegral: integral }) });
    mount('/integrals');
    await userEvent.type(screen.getByLabelText('Integral en LaTeX'), 'integral');
    await userEvent.click(screen.getByRole('button', { name: 'Calcular integral' }));
    expect(await screen.findByText('x^2/2 + C')).toBeInTheDocument();
    expect(calls.filter(c => c.operation === 'CalculateIntegral')).toHaveLength(1);
    await waitFor(() => expect(calls.filter(c => c.operation === 'IntegralHistory').length).toBeGreaterThan(1));
  });
  it('muestra failed como resultado de dominio y texto seguro', async () => {
    backend({ IntegralHistory: () => json({ integrals: page }), CalculateIntegral: () => json({ calculateIntegral: {
      ...integral, latex: '<script>alert(1)</script>', status: 'failed', result: null,
      error: { code: 'UNSOLVABLE', message: 'No se pudo resolver' },
    } }) });
    mount('/integrals');
    await userEvent.type(screen.getByLabelText('Integral en LaTeX'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Calcular integral' }));
    expect(await screen.findByText('<script>alert(1)</script>')).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
  it('conserva el texto ante error y no repite automáticamente', async () => {
    const { calls } = backend({ IntegralHistory: () => json({ integrals: page }), CalculateIntegral: () => error('UPSTREAM_TIMEOUT', 'integrals') });
    mount('/integrals');
    await userEvent.type(screen.getByLabelText('Integral en LaTeX'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Calcular integral' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByLabelText('Integral en LaTeX')).toHaveValue('x');
    expect(calls.filter(c => c.operation === 'CalculateIntegral')).toHaveLength(1);
  });
  it('filtra historial y consulta detalle', async () => {
    const { calls } = backend({ IntegralHistory: () => json({ integrals: { ...page, items: [integral], total: 1 } }),
      IntegralDetail: () => json({ integral }) });
    mount('/integrals');
    await userEvent.selectOptions(screen.getByLabelText('Estado'), 'failed');
    await waitFor(() => expect(calls.some(c => c.operation === 'IntegralHistory' && c.variables.status === 'failed')).toBe(true));
    await userEvent.click(await screen.findByRole('link', { name: 'integral' }));
    expect(await screen.findByText('x^2/2 + C')).toBeInTheDocument();
  });
});
