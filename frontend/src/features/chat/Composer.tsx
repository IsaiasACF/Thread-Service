import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Button, ErrorMessage } from '../../components/ui';
import { characterCount, writeError } from './errors';
import styles from './Chat.module.css';

export function Composer({ label, disabled, onSend, onRefresh, reply = false }: {
  label: string; disabled: boolean; onSend: (content: string) => Promise<void>; onRefresh: () => void; reply?: boolean;
}) {
  const [content, setContent] = useState('');
  const [validation, setValidation] = useState('');
  const sending = useMutation({ mutationFn: onSend, retry: false });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (disabled || sending.isPending) return;
    if (characterCount(content) < 1 || characterCount(content) > 4000 || (reply && !content.trim())) {
      setValidation('El contenido debe tener entre 1 y 4000 caracteres.'); return;
    }
    setValidation('');
    try { await sending.mutateAsync(content); setContent(''); }
    catch { /* Preserve the entire draft, including line breaks, on every error. */ }
  }
  const inputId = reply ? 'reply-content' : 'message-content';
  return <form onSubmit={submit} className={styles.composer}>
    <label htmlFor={inputId}>{label}</label>
    <textarea id={inputId} rows={3} value={content} onChange={event => { setContent(event.target.value); if (sending.isSuccess) sending.reset(); }} disabled={disabled || sending.isPending} placeholder={disabled ? 'Selecciona una identidad válida para escribir' : reply ? 'Continúa esta conversación…' : 'Comparte una idea con el canal…'} />
    {validation && <ErrorMessage message={validation} />}
    {sending.isError && <div><ErrorMessage message={writeError(sending.error)} /><button className={styles.textButton} type="button" onClick={onRefresh}>Actualizar {reply ? 'respuestas' : 'mensajes'} antes de repetir</button></div>}
    {sending.isSuccess && <p className={styles.success} role="status">{reply ? 'Respuesta publicada.' : 'Mensaje publicado.'}</p>}
    <div className={styles.composerFoot}><span>{characterCount(content)}/4000 · {reply ? 'Una respuesta al mensaje original' : 'Los saltos de línea se conservan'}</span>
      <Button type="submit" disabled={disabled || sending.isPending}>{sending.isPending ? 'Enviando…' : reply ? 'Publicar respuesta' : 'Enviar mensaje'}</Button></div>
  </form>;
}
