import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/auth/ProtectedRoute'
import Login from './pages/Login'
import Workspace from './pages/Workspace'
import KnowledgeBase from './pages/KnowledgeBase'
import AuditLog from './pages/AuditLog'

function App() {
  return (
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
  )
}

export default App
