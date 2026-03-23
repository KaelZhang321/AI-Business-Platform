import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { Spin } from 'antd'
import { useAppStore } from '../../stores/useAppStore'

interface ProtectedRouteProps {
  requiredAbility?: { action: string; subject: string }
}

export default function ProtectedRoute({ requiredAbility }: ProtectedRouteProps) {
  const { isAuthenticated, ability, restoreSession, token } = useAppStore()
  const [loading, setLoading] = useState(!isAuthenticated && !!token)

  useEffect(() => {
    if (!isAuthenticated && token) {
      restoreSession().finally(() => setLoading(false))
    }
  }, [isAuthenticated, token, restoreSession])

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (requiredAbility && ability) {
    const canAccess = ability.can(
      requiredAbility.action as never,
      requiredAbility.subject as never,
    )
    if (!canAccess) {
      return (
        <div className="h-screen flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-6xl font-bold text-gray-300">403</h1>
            <p className="text-gray-500 mt-2">暂无权限访问此页面</p>
          </div>
        </div>
      )
    }
  }

  return <Outlet />
}
