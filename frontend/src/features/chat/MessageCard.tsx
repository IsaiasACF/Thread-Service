import { useIdentity } from '../identity/IdentityProvider';
import type { Message } from './api';
import { Author } from './Author';
import styles from './Chat.module.css';

export function MessageCard({ message, onReplies, selected = false }: { message: Message; onReplies?: () => void; selected?: boolean }) {
  const own = useIdentity().user?.id === message.authorId;
  const date = new Date(message.createdAt);
  return <article className={`${styles.message} ${own ? styles.ownMessage : ''}`} aria-label={`Mensaje ${message.id}`}>
    <div className={styles.messageMeta}><Author id={message.authorId} />{own && <span>Tú</span>}
      <time dateTime={message.createdAt}>{Number.isNaN(date.getTime()) ? message.createdAt : date.toLocaleString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</time>
    </div>
    <p className={styles.messageContent}>{message.content}</p>
    {onReplies && <button className={styles.replyAction} aria-expanded={selected} onClick={onReplies}>Ver respuestas</button>}
  </article>;
}
