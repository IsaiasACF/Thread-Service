import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';

export const THEME_STORAGE_KEY = 'thread.theme.v1';
type Theme = 'light' | 'dark';

function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
  } catch { /* The theme remains usable without browser storage. */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeToggle() {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#141416' : '#FFFFFF');
    try { localStorage.setItem(THEME_STORAGE_KEY, theme); } catch { /* Session preference only. */ }
  }, [theme]);
  return <button type="button" aria-pressed={theme === 'dark'}
    onClick={() => setTheme(current => current === 'dark' ? 'light' : 'dark')}>
    <Icon name={theme === 'dark' ? 'moon' : 'sun'} />Modo oscuro <span aria-hidden="true" data-switch="true" data-on={theme === 'dark'} />
  </button>;
}
