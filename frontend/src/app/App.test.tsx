import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { App } from './App';
import { Providers } from './Providers';
import { graphqlClient } from '../lib/graphql';

function mount(path = '/') {
  return render(<Providers><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></Providers>);
}

describe('Rutas compartidas', () => {
  it.each([
    ['/', 'Identidad'], ['/channels/c-1', 'Chat y respuestas'],
    ['/integrals', 'Calculadora e historial'], ['/integrals/i-1', 'Detalle de integral'],
    ['/polls/p-1', 'Encuesta'], ['/no-existe', 'Página no encontrada'],
  ])('abre %s sin consultar servicios', (path, title) => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('No network allowed'));
    mount(path);
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.getByText('Pendiente de implementación')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockRestore();
  });

  it('permite navegar con enlaces accesibles', async () => {
    const user = userEvent.setup();
    mount();
    for (const [label, heading] of [['Chat', 'Chat y respuestas'], ['Integrales', 'Calculadora e historial'], ['Encuestas', 'Encuesta'], ['Identidad', 'Identidad']]) {
      await user.click(screen.getByRole('link', { name: label }));
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page');
    }
  });

  it('usa el endpoint GraphQL común', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(
      JSON.stringify({ data: { health: 'ok' } }),
      { headers: { 'Content-Type': 'application/json' } },
    ));
    try {
      expect(await graphqlClient.request('{ health }')).toEqual({ health: 'ok' });
      expect(fetch).toHaveBeenCalledWith(expect.objectContaining({ pathname: '/graphql' }), expect.anything());
    } finally { fetch.mockRestore(); }
  });
});
