import { useEffect, useState } from 'react';
import { Icon } from './Icon';
import styles from './ui.module.css';

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'error'>('idle');
  useEffect(() => {
    if (state === 'idle') return;
    const timeout = setTimeout(() => setState('idle'), 2000);
    return () => clearTimeout(timeout);
  }, [state]);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setState('copied'); }
    catch { setState('error'); }
  }
  return <span className={styles.copyControl}>
    <button type="button" className={styles.copyButton} aria-label={label} onClick={() => void copy()}>
      <Icon name={state === 'copied' ? 'check' : 'copy'} />{state === 'copied' ? 'Copiado' : 'Copiar'}
    </button>
    <span role="status" className={styles.copyStatus}>{state === 'error' ? 'No se pudo copiar. Selecciona el texto para copiarlo.' : state === 'copied' ? 'Copiado al portapapeles.' : ''}</span>
  </span>;
}
