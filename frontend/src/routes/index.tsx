import { RouteObject } from 'react-router-dom'
import MainLayout from '../layouts/MainLayout'
import Workspace from '../pages/Workspace'
import KnowledgeBase from '../pages/KnowledgeBase'

export const routes: RouteObject[] = [
  {
    element: <MainLayout />,
    children: [
      { path: '/', element: <Workspace /> },
      { path: '/workspace', element: <Workspace /> },
      { path: '/knowledge', element: <KnowledgeBase /> },
    ],
  },
]
