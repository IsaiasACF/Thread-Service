import { Link, NavLink, Outlet, useRoutes, type RouteObject } from 'react-router-dom';
import { Placeholder } from '../components/ui';
import styles from './Layout.module.css';

const modules = import.meta.glob<{ routes: RouteObject[] }>('../features/*/routes.tsx', { eager: true });
const featureRoutes = Object.keys(modules).sort().flatMap((key) => modules[key].routes);

function Layout() {
  return <>
    <a className={styles.skip} href="#main">Saltar al contenido</a>
    <header className={styles.header}>
      <Link className={styles.brand} to="/">Thread<span>Espacio compartido</span></Link>
      <nav aria-label="Navegación principal" className={styles.nav}>
        <NavLink to="/" end>Identidad</NavLink>
        <NavLink to="/channels/pendiente">Chat</NavLink>
        <NavLink to="/integrals">Integrales</NavLink>
        <NavLink to="/polls/pendiente">Encuestas</NavLink>
      </nav>
    </header>
    <main id="main" tabIndex={-1} className={styles.main}><Outlet /></main>
    <footer className={styles.footer}>Thread · Tarea 6 · Interfaz en construcción</footer>
  </>;
}

export function App() {
  return useRoutes([{ element: <Layout />, children: [
    ...featureRoutes,
    { path: '*', element: <Placeholder title="Página no encontrada" description="Usa la navegación para volver a una sección disponible." /> },
  ] }]);
}
