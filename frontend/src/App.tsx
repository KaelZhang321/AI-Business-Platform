import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Workspace from './pages/Workspace'
import KnowledgeBase from './pages/KnowledgeBase'

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<Navigate to="/workspace" replace />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/knowledge" element={<KnowledgeBase />} />
      </Route>
    </Routes>
  )
}

export default App
