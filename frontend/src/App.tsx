import { Routes, Route, Navigate } from 'react-router-dom'
import { createMongoAbility } from '@casl/ability'
import type { AppAbility } from './abilities'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/auth/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { AbilityContext } from './components/auth/Can'
import { useAppStore } from './stores/useAppStore'
import Login from './pages/Login'
import Workspace from './pages/Workspace'
import KnowledgeBase from './pages/KnowledgeBase'
import AuditLog from './pages/AuditLog'

const defaultAbility = createMongoAbility() as AppAbility

function App() {
  const ability = useAppStore((s) => s.ability)

  return (
    <ErrorBoundary>
    <AbilityContext.Provider value={ability ?? defaultAbility}>
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
    </AbilityContext.Provider>
    </ErrorBoundary>
  )
}

export default App
