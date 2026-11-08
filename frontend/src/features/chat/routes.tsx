import type { RouteObject } from 'react-router-dom';
import ChatPage from './ChatPage';
export const routes: RouteObject[] = [{ path: '/channels', element: <ChatPage /> }, { path: '/channels/:channelId', element: <ChatPage /> }];
