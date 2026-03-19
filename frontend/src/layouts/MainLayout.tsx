import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DesktopOutlined,
  BookOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import AIChat from '../components/chat/AIChat'

const { Sider, Content } = Layout

const menuItems = [
  { key: '/workspace', icon: <DesktopOutlined />, label: '工作台' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
]

export default function MainLayout() {
  const [chatVisible, setChatVisible] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

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
