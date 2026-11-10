import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { backend, json, mount } from '../features/chat/testSupport';
import { THEME_STORAGE_KEY } from './ThemeToggle';

describe('Estructura y tema compartidos', () => {
  it('mantiene la barra lateral, el borrador y el tema al cambiar de sección', async () => {
    backend({ IntegralHistory: () => json({ integrals: { items: [], total: 0, limit: 20, offset: 0 } }) });
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    mount('/channels');
    const sidebar = screen.getByRole('complementary', { name: 'Canales y herramientas' });
    await userEvent.click(screen.getByRole('button', { name: 'Crear canal' }));
    await userEvent.type(screen.getByLabelText('Nombre del canal'), 'Borrador');
    await userEvent.click(screen.getByRole('button', { name: 'Modo oscuro' }));
    await userEvent.click(screen.getByRole('link', { name: 'Integrales' }));
    expect(screen.getByRole('heading', { name: 'Calculadora e historial' })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Canales y herramientas' })).toBe(sidebar);
    expect(screen.getByLabelText('Nombre del canal')).toHaveValue('Borrador');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('button', { name: 'Modo oscuro' })).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });
  it('recupera la preferencia guardada y permite volver al tema claro', async () => {
    backend(); localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    const first = mount('/channels');
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));
    first.unmount();
    mount('/polls/pendiente');
    expect(screen.getByRole('button', { name: 'Modo oscuro' })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(screen.getByRole('button', { name: 'Modo oscuro' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });
});
