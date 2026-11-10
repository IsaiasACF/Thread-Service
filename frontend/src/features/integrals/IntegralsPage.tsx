import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { Icon } from '../../components/Icon';
import { readError } from '../chat/errors';
import { calculateIntegral, getIntegrals } from './api';
import { IntegralResult } from './IntegralResult';
import styles from './Integrals.module.css';

export default function IntegralsPage() {
  const [latex, setLatex] = useState('');
  const editor = useRef<HTMLTextAreaElement>(null);
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const cache = useQueryClient();
  const history = useQuery({ queryKey: ['integrals', status, offset], retry: false,
    queryFn: ({ signal }) => getIntegrals(20, offset, status || null, signal) });
  const calculation = useMutation({ mutationFn: calculateIntegral, retry: false,
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['integrals'] }); } });
  function submit(event: FormEvent) {
    event.preventDefault();
    if (latex.trim() && !calculation.isPending) calculation.mutate(latex.trim());
  }
  return <section className={styles.page}>
    <div className={styles.heading}><span className={styles.headingIcon}><Icon name="calculator" /></span><h1>Calculadora e historial</h1></div>
    <p>Escribe una integral en LaTeX. El cálculo se guarda aunque no se pueda resolver.</p>
    <div className={styles.workbench}><div className={styles.editorPane}>
    <form className={styles.form} onSubmit={submit}>
      <label htmlFor="latex">Integral en LaTeX</label>
      <div className={styles.examples}><span>Ejemplos</span>{[
        ['Integral definida', '\\int_0^1 x^2 \\, dx'], ['Integral indefinida', '\\int x \\, dx'],
      ].map(([label, value]) => <button key={label} type="button" disabled={calculation.isPending} aria-pressed={latex === value}
        onClick={() => { setLatex(value); editor.current?.focus(); }}>{label}</button>)}</div>
      <textarea ref={editor} id="latex" value={latex} onChange={e => setLatex(e.target.value)} required maxLength={1000}
        placeholder={'\\int_0^1 x^2 \\, dx'} disabled={calculation.isPending} />
      <Button type="submit" disabled={!latex.trim() || calculation.isPending}>{calculation.isPending ? 'Calculando…' : 'Calcular integral'}</Button>
    </form>
    {calculation.isError && <><ErrorMessage message={readError(calculation.error)} /><p>Tu texto se conserva. Si se perdió la respuesta, revisa el historial antes de volver a calcular.</p></>}
    {calculation.data && <><IntegralResult integral={calculation.data} /><Link to={`/integrals/${encodeURIComponent(calculation.data.id)}`}>Abrir detalle del cálculo</Link></>}
    </div><section className={styles.historyPane}>
    <h2>Historial</h2>
    <div className={styles.toolbar}>
      <label>Estado <select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
        <option value="">Todos</option><option value="calculated">Calculadas</option><option value="failed">Fallidas</option>
      </select></label>
      <Button onClick={() => void history.refetch()} disabled={history.isFetching}>Actualizar historial</Button>
    </div>
    {history.isPending && <LoadingIndicator />}
    {history.isError && <ErrorMessage message={readError(history.error)} />}
    {history.data && <>
      {history.data.items.length === 0 && <EmptyState>No hay cálculos para este filtro.</EmptyState>}
      {history.data.items.map(item => <article key={item.id} className={styles.result}>
        <Link to={`/integrals/${encodeURIComponent(item.id)}`}>{item.latex}</Link>
        <p><span className={styles.status}>{item.status === 'calculated' ? 'Calculada' : 'Fallida'}</span> · {new Date(item.createdAt).toLocaleString('es-CL')}</p>
      </article>)}
      <div className={styles.toolbar}>
        <Button disabled={offset === 0 || history.isFetching} onClick={() => setOffset(Math.max(0, offset - 20))}>Anterior</Button>
        <span>{history.data.total} cálculos · Página {Math.floor(offset / 20) + 1}</span>
        <Button disabled={offset + 20 >= history.data.total || history.isFetching} onClick={() => setOffset(offset + 20)}>Siguiente</Button>
      </div>
    </>}
    </section></div>
  </section>;
}
