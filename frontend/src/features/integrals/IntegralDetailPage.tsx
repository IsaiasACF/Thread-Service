import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { readError } from '../chat/errors';
import { getIntegral } from './api';
import { IntegralResult } from './IntegralResult';
import styles from './Integrals.module.css';

export default function IntegralDetailPage() {
  const { id = '' } = useParams();
  const detail = useQuery({ queryKey: ['integral', id], retry: false,
    queryFn: ({ signal }) => getIntegral(id, signal), enabled: Boolean(id) });
  return <section className={styles.page}><h1>Detalle de integral</h1>
    <Link to="/integrals">Volver a calculadora e historial</Link>
    {detail.isPending && <LoadingIndicator />}
    {detail.isError && <><ErrorMessage message={readError(detail.error)} /><Button onClick={() => void detail.refetch()}>Reintentar consulta</Button></>}
    {detail.isSuccess && (detail.data ? <IntegralResult integral={detail.data} /> : <EmptyState>El cálculo no existe.</EmptyState>)}
  </section>;
}
