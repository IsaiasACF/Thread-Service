import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';
import styles from './ui.module.css';

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} type={props.type ?? 'button'} className={`${styles.button} ${props.className ?? ''}`} />;
}
export function LoadingIndicator() {
  return <p role="status" aria-live="polite">Cargando…</p>;
}
export function ErrorMessage({ message = 'No se pudo completar la solicitud.' }: { message?: string }) {
  return <p role="alert" className={styles.error}>{message}</p>;
}
export function EmptyState({ children }: PropsWithChildren) {
  return <div className={styles.empty}>{children}</div>;
}
export function Placeholder({ title, description, detail }: { title: string; description: string; detail?: string }) {
  return <section className={styles.panel} aria-labelledby="page-title">
    <span className={styles.badge}>Pendiente de implementación</span>
    <h1 id="page-title">{title}</h1><p>{description}</p>
    {detail && <p className={styles.detail}>{detail}</p>}
    <EmptyState>Esta sección estará disponible en una próxima entrega.</EmptyState>
  </section>;
}
