import type { Integral } from './api';
import styles from './Integrals.module.css';

export function IntegralResult({ integral }: { integral: Integral }) {
  return <article className={styles.result} aria-label="Resultado de integral">
    <p><strong>{integral.status === 'calculated' ? 'Calculada' : 'No se pudo resolver'}</strong></p>
    <pre className={styles.formula} aria-label="Integral en LaTeX">{integral.latex}</pre>
    {integral.result && <>
      <pre className={styles.formula} aria-label="Resultado en LaTeX">{integral.result.latex}{integral.result.indefinite ? ' + C' : ''}</pre>
      {integral.result.numeric !== null && <p>Valor numérico: {integral.result.numeric}</p>}
    </>}
    {integral.error && <p role="status">{integral.error.message} ({integral.error.code})</p>}
    <p>{new Date(integral.createdAt).toLocaleString('es-CL')} · {integral.durationMs} ms · Origen: {integral.source.kind}</p>
  </article>;
}
