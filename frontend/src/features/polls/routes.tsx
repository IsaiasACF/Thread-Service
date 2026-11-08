import type { RouteObject } from 'react-router-dom';
import PollPage from './PollPage';
export const routes: RouteObject[] = [{ path: '/polls/:pollId', element: <PollPage /> }];
