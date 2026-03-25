import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import { createMongoAbility } from '@casl/ability'
import type { AppAbility } from './abilities'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/auth/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { AbilityContext } from './components/auth/Can'
import { useAppStore } from './stores/useAppStore'

const Login = lazy(() => import('./pages/Login'))
const Workspace = lazy(() => import('./pages/Workspace'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const AuditLog = lazy(() => import('./pages/AuditLog'))

const defaultAbility = createMongoAbility() as AppAbility

const PageFallback = (
  <div className="h-64 flex items-center justify-center"><Spin size="large" /></div>
)

function App() {
  const ability = useAppStore((s) => s.ability)

  return (
    <ErrorBoundary>
    <AbilityContext.Provider value={ability ?? defaultAbility}>
    <Suspense fallback={PageFallback}>
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/workspace" replace />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/knowledge" element={<KnowledgeBase />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute requiredAbility={{ action: 'read', subject: 'Audit' }} />}>
        <Route element={<MainLayout />}>
          <Route path="/audit" element={<AuditLog />} />
        </Route>
      </Route>
    </Routes>
    </Suspense>
    </AbilityContext.Provider>
    </ErrorBoundary>
  )
}

export default App
