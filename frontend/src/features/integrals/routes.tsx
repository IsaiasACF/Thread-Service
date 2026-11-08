import type { RouteObject } from 'react-router-dom';
import IntegralsPage from './IntegralsPage';
import IntegralDetailPage from './IntegralDetailPage';
export const routes: RouteObject[] = [{ path: '/integrals', element: <IntegralsPage /> }, { path: '/integrals/:id', element: <IntegralDetailPage /> }];
