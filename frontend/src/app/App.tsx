import { Link, Outlet, useLocation, useRoutes, type RouteObject } from 'react-router-dom';
import styles from './Layout.module.css';
import { IdentityProvider } from '../features/identity/IdentityProvider';
import { Workspace } from '../features/chat/Workspace';
import { ThemeToggle } from './ThemeToggle';

const modules = import.meta.glob<{ routes: RouteObject[] }>('../features/*/routes.tsx', { eager: true });
const featureRoutes = Object.keys(modules).sort().flatMap((key) => modules[key].routes);

function Layout() {
  const { pathname } = useLocation();
  const section = pathname.startsWith('/integrals') ? 'Integrales'
    : pathname.startsWith('/polls') ? 'Encuestas'
    : pathname.startsWith('/channels') ? 'Chat' : pathname === '/' ? 'Identidad' : 'Página no encontrada';
  return <Workspace>
    <a className={styles.skip} href="#main">Saltar al contenido</a>
    <header className={styles.header}><span>{section}</span><ThemeToggle /></header>
    <main id="main" tabIndex={-1} className={styles.main}><Outlet /></main>
  </Workspace>;
}

export function App() {
  const routes = useRoutes([{ element: <Layout />, children: [
    ...featureRoutes,
    { path: '*', element: <section className={styles.notFound}><h1>Página no encontrada</h1><p>La dirección no corresponde a una página disponible.</p><Link to="/channels">Volver al chat</Link></section> },
  ] }]);
  return <IdentityProvider>{routes}</IdentityProvider>;
}
