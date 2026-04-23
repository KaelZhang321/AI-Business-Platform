import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Alert, Button, Card, Space, Typography } from 'antd'

const { Paragraph, Text, Title } = Typography

/**
 * SSO 回调页面：处理企业统一认证返回的授权码或错误信息。
 * 支持子路径部署场景（如 /ai-platform/sso/callback）。
 */
export default function SsoCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  /** 解析 URL 查询参数中的回调状态（error / code / 无参数） */
  const callbackState = useMemo(() => {
    const error = searchParams.get('error')
    const errorDescription = searchParams.get('error_description')
    const code = searchParams.get('code')

    if (error) {
      return {
        status: 'error' as const,
        title: '企业 SSO 登录失败',
        description: errorDescription || error,
      }
    }

    if (code) {
      return {
        status: 'warning' as const,
        title: '已收到 SSO 回调',
        description: '当前前端已兼容子路径回调，但尚未接入授权码兑换接口，请先使用账号密码登录。',
      }
    }

    return {
      status: 'info' as const,
      title: '未检测到 SSO 回调参数',
      description: '请从登录页重新发起企业 SSO 登录。',
    }
  }, [searchParams])

  return (
    <div className="h-screen flex items-center justify-center bg-gray-100 px-4">
      <Card className="w-full max-w-xl shadow-lg">
        <Space direction="vertical" size="large" className="w-full">
          <div>
            <Title level={3}>{callbackState.title}</Title>
            <Paragraph type="secondary">
              当前页面已兼容子路径部署场景，例如 <Text code>/ai-platform/sso/callback</Text>。
            </Paragraph>
          </div>

          <Alert
            type={callbackState.status}
            showIcon
            message={callbackState.title}
            description={callbackState.description}
          />

          <div className="flex justify-end">
            <Button type="primary" onClick={() => navigate('/login', { replace: true })}>
              返回登录页
            </Button>
          </div>
        </Space>
      </Card>
    </div>
  )
}
