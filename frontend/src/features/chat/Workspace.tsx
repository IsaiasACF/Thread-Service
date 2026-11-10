import { useEffect, useRef, useState, type FormEvent, type PropsWithChildren } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, EmptyState, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { Icon } from '../../components/Icon';
import { useIdentity } from '../identity/IdentityProvider';
import { channelKey, channelsKey, createChannel, getChannels } from './api';
import { characterCount, readError, writeError } from './errors';
import styles from './Chat.module.css';

export function Workspace({ children }: PropsWithChildren) {
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [expanded, setExpanded] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [filter, setFilter] = useState('');
  const [validation, setValidation] = useState('');
  const identity = useIdentity();
  const cache = useQueryClient();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const currentPath = useRef(pathname);
  currentPath.current = pathname;
  useEffect(() => { setExpanded(false); }, [pathname]);
  const channels = useQuery({ queryKey: channelsKey, queryFn: ({ signal }) => getChannels(signal), retry: false });
  const activeChannel = channels.data?.find(channel => pathname === `/channels/${encodeURIComponent(channel.id)}`);
  const creation = useMutation({ mutationFn: createChannel, retry: false });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (creation.isPending) return;
    const value = name.trim();
    if (!value || characterCount(value) > 80) { setValidation('El nombre debe tener entre 1 y 80 caracteres.'); return; }
    setValidation('');
    const startingPath = currentPath.current;
    try {
      const channel = await creation.mutateAsync(value);
      cache.setQueryData(channelKey(channel.id), channel);
      await cache.invalidateQueries({ queryKey: channelsKey });
      if (alive.current) {
        setName(''); setCreating(false); setExpanded(false);
        if (currentPath.current === startingPath) navigate(`/channels/${encodeURIComponent(channel.id)}`);
      }
    } catch { /* Mutation state is presented below; keep the draft. */ }
  }
  return <div className={styles.workspace}>
    <aside className={styles.sidebar} aria-label="Canales y herramientas">
      <Link to="/" className={styles.brand}><span className={styles.brandIcon}><Icon name="chat" /></span>Thread<span className={styles.brandRule} aria-hidden="true" /></Link>
      <button className={styles.mobileToggle} aria-expanded={expanded} aria-controls="workspace-navigation" onClick={() => setExpanded(!expanded)}>Canales y navegación</button>
      <div id="workspace-navigation" className={`${styles.sidebarContent} ${expanded ? styles.expanded : ''}`}>
        <div className={styles.identityCard}>
          <span className={styles.avatar}>{(identity.user ? Array.from(identity.user.displayName)[0]?.toUpperCase() : undefined) ?? '?'}</span>
          <div><strong>{identity.checking ? 'Validando identidad…' : identity.user?.displayName ?? 'Sin identidad activa'}</strong>
            <Link to="/">{identity.user ? 'Cambiar identidad' : 'Elegir identidad'}</Link></div>
          {identity.storedId && <button className={styles.iconButton} aria-label="Cerrar identidad local" onClick={identity.clear}>Salir</button>}
        </div>
        {identity.error && <div className={styles.sideError}><ErrorMessage message={identity.error} /><button onClick={identity.refresh} className={styles.textButton}>Revalidar identidad</button></div>}
        <div className={styles.sectionTitle}><h2>Canales {channels.data && <span className={styles.channelCount}>{channels.data.length}</span>}</h2><button className={styles.iconButton} aria-label="Crear canal" aria-expanded={creating} onClick={() => setCreating(!creating)}><Icon name="plus" />Crear</button></div>
        <div className={styles.channelSearch}><Icon name="search" /><input type="search" aria-label="Buscar canales" placeholder="Buscar canales" value={filter} onChange={event => setFilter(event.target.value)} /></div>
        {creating && <form onSubmit={submit} className={styles.channelForm}>
          <label htmlFor="channel-name">Nombre del canal</label>
          <input id="channel-name" value={name} onChange={event => setName(event.target.value)} disabled={creation.isPending} autoFocus />
          {validation && <ErrorMessage message={validation} />}
          {creation.isError && <><ErrorMessage message={writeError(creation.error)} /><button type="button" className={styles.textButton} onClick={() => { void channels.refetch(); }}>Actualizar canales antes de repetir</button></>}
          <Button type="submit" disabled={creation.isPending}>{creation.isPending ? 'Creando…' : 'Crear y abrir'}</Button>
        </form>}
        {channels.isPending && <div className={styles.sidebarFeedback}><LoadingIndicator /></div>}
        {channels.isError && <><ErrorMessage message={readError(channels.error)} /><button className={styles.textButton} onClick={() => { void channels.refetch(); }}>Actualizar canales</button></>}
        {channels.isSuccess && channels.data.length === 0 && <div className={styles.sidebarFeedback}><EmptyState>Todavía no hay canales. Crea el primero.</EmptyState></div>}
        <nav aria-label="Canales disponibles" className={styles.channelList}>
          {channels.data?.filter(channel => channel.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase())).map(channel => <NavLink key={channel.id} to={`/channels/${encodeURIComponent(channel.id)}`} onClick={() => setExpanded(false)}><Icon name="chat" /><span>{channel.name}</span></NavLink>)}
          {filter && channels.data && !channels.data.some(channel => channel.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase())) && <p className={styles.noMatches}>No hay canales que coincidan.</p>}
        </nav>
        <nav className={styles.tools} aria-label="Herramientas">
          <NavLink to="/" end><Icon name="user" />Identidad</NavLink>
          <NavLink to="/channels"><Icon name="chat" />Chat</NavLink>
          <NavLink to="/integrals"><Icon name="calculator" />Integrales</NavLink>
          <Link to={activeChannel ? `/polls/pendiente?channel=${encodeURIComponent(activeChannel.id)}` : '/polls/pendiente'} aria-current={pathname.startsWith('/polls') ? 'page' : undefined}><Icon name="poll" />Encuestas</Link>
        </nav>
      </div>
    </aside>
    <div className={styles.desk}>{children}</div>
  </div>;
}
