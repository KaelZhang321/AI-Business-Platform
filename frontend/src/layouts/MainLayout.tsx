import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Dropdown, Avatar, Space } from 'antd'
import {
  DesktopOutlined,
  BookOutlined,
  RobotOutlined,
  AuditOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import AIChat from '../components/chat/AIChat'
import { useAppStore } from '../stores/useAppStore'

const { Sider, Header, Content } = Layout

const allMenuItems = [
  { key: '/workspace', icon: <DesktopOutlined />, label: '工作台' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: '/audit', icon: <AuditOutlined />, label: '审计日志', requiredRole: 'admin' },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { chatVisible, setChatVisible, user, ability, logout } = useAppStore()

  const menuItems = allMenuItems
    .filter((item) => {
      if (!item.requiredRole) return true
      if (!ability) return false
      return ability.can('read', 'Audit')
    })
    .map(({ requiredRole: _, ...item }) => item)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const userMenuItems = [
    {
      key: 'role',
      label: `角色: ${user?.role ?? '-'}`,
      disabled: true,
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <Layout className="h-screen">
      <Sider width={200} theme="light" className="border-r border-gray-200">
        <div className="h-14 flex items-center justify-center border-b border-gray-200">
          <RobotOutlined className="text-xl mr-2" />
          <span className="font-bold text-base">AI业务中台</span>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          className="border-r-0"
        />
      </Sider>
      <Layout>
        <Header className="h-14 flex items-center justify-end px-6 bg-white border-b border-gray-200"
          style={{ padding: '0 24px' }}>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space className="cursor-pointer">
              <Avatar size="small" icon={<UserOutlined />} />
              <span className="text-sm">{user?.displayName ?? user?.username ?? '用户'}</span>
            </Space>
          </Dropdown>
        </Header>
        <Layout className="flex flex-row">
          {chatVisible && (
            <div className="w-96 border-r border-gray-200 flex flex-col">
              <AIChat onClose={() => setChatVisible(false)} />
            </div>
          )}
          <Content className="p-6 overflow-auto bg-gray-50">
            {!chatVisible && (
              <button
                onClick={() => setChatVisible(true)}
                className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center shadow-lg hover:bg-blue-600 z-50"
              >
                <RobotOutlined className="text-lg" />
              </button>
            )}
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}
