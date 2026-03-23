import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined, RobotOutlined } from '@ant-design/icons'
import { useAppStore } from '../stores/useAppStore'

export default function Login() {
  const navigate = useNavigate()
  const login = useAppStore((s) => s.login)
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/workspace', { replace: true })
    } catch {
      message.error('用户名或密码错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-96 shadow-lg">
        <div className="text-center mb-6">
          <RobotOutlined className="text-4xl text-blue-500" />
          <h1 className="text-xl font-bold mt-2">AI 业务中台</h1>
          <p className="text-gray-500 text-sm">请登录以继续</p>
        </div>
        <Form onFinish={onFinish} autoComplete="off" size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
