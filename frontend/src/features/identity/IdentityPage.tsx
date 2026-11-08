import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button, ErrorMessage, LoadingIndicator } from '../../components/ui';
import { Workspace } from '../chat/Workspace';
import { characterCount, errorCode, readError } from '../chat/errors';
import { createUser, getUser, userKey } from './api';
import { useIdentity } from './IdentityProvider';
import styles from '../chat/Chat.module.css';

export default function IdentityPage() {
  const identity = useIdentity();
  const alive = useRef(true);
  const currentId = useRef(identity.storedId);
  currentId.current = identity.storedId;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const [name, setName] = useState('');
  const [id, setId] = useState('');
  const [validation, setValidation] = useState('');
  const cache = useQueryClient();
  const creation = useMutation({ mutationFn: createUser, retry: false });
  const lookup = useMutation({ mutationFn: async (value: string) => {
    const user = await getUser(value);
    if (!user) throw new Error('missing-user');
    cache.setQueryData(userKey(value), user);
    return user;
  }, retry: false });
  const pending = creation.isPending || lookup.isPending;
  async function create(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    if (!name.trim() || characterCount(name.trim()) > 80) { setValidation('El nombre debe tener entre 1 y 80 caracteres.'); return; }
    setValidation(''); lookup.reset();
    const startingId = currentId.current;
    try {
      const user = await creation.mutateAsync(name.trim());
      if (alive.current && currentId.current === startingId) { identity.choose(user); setName(''); }
    }
    catch { /* Keep input on failure. */ }
  }
  async function select(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    if (!id.trim()) { setValidation('Ingresa un ID de usuario.'); return; }
    setValidation(''); creation.reset();
    const startingId = currentId.current;
    try {
      const user = await lookup.mutateAsync(id.trim());
      if (alive.current && currentId.current === startingId) { identity.choose(user); setId(''); }
    }
    catch { /* Keep input on failure. */ }
  }
  return <Workspace><div className={styles.identityPage}>
    <span className={styles.eyebrow}>TU ESPACIO DE CONVERSACIÓN</span>
    <h1>Las buenas ideas empiezan<br />con una conversación.</h1>
    <p className={styles.intro}>Elige cómo quieres participar. Tu identidad se guarda en este navegador para volver a tus conversaciones.</p>
    {identity.checking && <LoadingIndicator />}
    {identity.storageWarning && <ErrorMessage message={identity.storageWarning} />}
    {identity.error && <ErrorMessage message={identity.error} />}
    {identity.user && <section className={styles.activeIdentity} aria-label="Identidad seleccionada">
      <span className={styles.avatar}>{Array.from(identity.user.displayName)[0]?.toUpperCase()}</span>
      <div><strong>Hola, {identity.user.displayName}</strong><p>Tu ID: <code>{identity.user.id}</code></p></div>
      <Link to="/channels" className={styles.primaryLink}>Ir a conversaciones →</Link>
    </section>}
    <div className={styles.identityForms}>
      <form onSubmit={create} className={styles.identityForm}>
        <span className={styles.step}>01</span><h2>Crea tu identidad</h2><p>Un nombre para que el resto sepa quién escribe.</p>
        <label htmlFor="display-name">Tu nombre</label><input id="display-name" autoComplete="nickname" value={name} onChange={event => setName(event.target.value)} disabled={pending} placeholder="¿Cómo te llamas?" />
        {creation.isError && <ErrorMessage message={errorCode(creation.error) === 'VALIDATION_ERROR' ? readError(creation.error) : 'No pudimos confirmar la creación. El resultado es incierto; revisa el servicio antes de crear otra identidad.'} />}
        <Button type="submit" disabled={pending}>{creation.isPending ? 'Creando identidad…' : 'Crear identidad'}</Button>
      </form>
      <form onSubmit={select} className={styles.identityForm}>
        <span className={styles.step}>02</span><h2>¿Ya tienes un ID?</h2><p>Recupera una identidad existente con su identificador.</p>
        <label htmlFor="existing-user">ID de usuario</label><input id="existing-user" value={id} onChange={event => setId(event.target.value)} disabled={pending} placeholder="Pega tu identificador" autoCapitalize="none" spellCheck={false} />
        {lookup.isError && <ErrorMessage message={lookup.error.message === 'missing-user' || errorCode(lookup.error) === 'NOT_FOUND' ? 'No encontramos esa identidad.' : readError(lookup.error)} />}
        <Button type="submit" disabled={pending}>{lookup.isPending ? 'Validando…' : 'Usar este ID'}</Button>
      </form>
    </div>
    {validation && <ErrorMessage message={validation} />}
    <p className={styles.identityNote}>Identidad local, sin contraseñas. Este selector no es un sistema de autenticación segura.</p>
  </div></Workspace>;
}
