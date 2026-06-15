import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useInterfaceValidationWS } from '../hooks/useInterfaceValidationWS'
import ValidationToaster from './ValidationToaster'
import GlobalSearch from './GlobalSearch'

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const location = useLocation()
  const { user, logout, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/login')
    }
  }, [isAuthenticated, isLoading, navigate])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600 dark:text-slate-400">加载中...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return <LayoutShell user={user} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} searchQuery={searchQuery} setSearchQuery={setSearchQuery} location={location} logout={logout} />
}

interface LayoutShellProps {
  user: ReturnType<typeof useAuth>['user']
  sidebarOpen: boolean
  setSidebarOpen: (v: boolean) => void
  searchQuery: string
  setSearchQuery: (v: string) => void
  location: ReturnType<typeof useLocation>
  logout: () => void
}

const LayoutShell = ({ user, sidebarOpen, setSidebarOpen, location, logout }: LayoutShellProps) => {
  // S3-1: keep the interface validation WebSocket alive for the whole session
  useInterfaceValidationWS(user?.tenant_id)


  const mainNavigation = [
    { name: '仪表盘', href: '/dashboard', icon: '📊' },
    { name: '知识图谱', href: '/knowledge-graph', icon: '🕸️' },
    { name: '文档管理', href: '/documents', icon: '📁' },
    { name: '决策流', href: '/decision-flow', icon: '⚙️' },
    { name: 'Workshop', href: '/workshop', icon: '🛠️' },
    { name: '分析报表', href: '/analytics', icon: '📈' },
  ]

  const ontologyNavigation = [
    { name: '对象类型', href: '/ontology/object-types', icon: '📦' },
    { name: '关系类型', href: '/ontology/link-types', icon: '🔗' },
    { name: '接口契约', href: '/ontology/interfaces', icon: '📋' },
    { name: '动作类型', href: '/ontology/action-types', icon: '⚡' },
    { name: '函数库', href: '/ontology/functions', icon: '🔧' },
    { name: '语义搜索', href: '/ontology/search', icon: '🔍' },
  ]

  const aipNavigation = [
    { name: 'AI 对话', href: '/aip/chat', icon: '🤖' },
    { name: 'RAG 搜索', href: '/aip/rag', icon: '🔍' },
    { name: 'AI Agent', href: '/aip/agents', icon: '🧠' },
    { name: 'Prompt 管理', href: '/aip/prompts', icon: '📝' },
  ]

  const systemNavigation = [
    { name: '系统设置', href: '/settings', icon: '🔧' },
  ]

  const isActive = (href: string) => location.pathname === href || location.pathname.startsWith(href + '/')

  const NavItem = ({ item }: { item: { name: string; href: string; icon: string } }) => (
    <li>
      <Link
        to={item.href}
        className={`flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 cursor-pointer text-sm ${
          isActive(item.href)
            ? 'bg-primary/10 text-primary font-semibold'
            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
        }`}
      >
        <span className="text-lg">{item.icon}</span>
        <span>{item.name}</span>
      </Link>
    </li>
  )

  const NavGroup = ({ title, items }: { title: string; items: typeof mainNavigation }) => (
    <div className="mb-4">
      <h3 className="px-4 text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2">
        {title}
      </h3>
      <ul className="space-y-1">
        {items.map((item) => (
          <NavItem key={item.name} item={item} />
        ))}
      </ul>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 z-40 h-screen transition-transform ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 w-64`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-center h-16 border-b border-slate-200 dark:border-slate-700">
            <h1 className="text-xl font-bold text-primary">
              🔷 Meatapivot
            </h1>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4">
            <NavGroup title="核心应用" items={mainNavigation} />
            <NavGroup title="本体语义层" items={ontologyNavigation} />
            <NavGroup title="AIP 智能层" items={aipNavigation} />
            <NavGroup title="系统" items={systemNavigation} />
          </nav>

          {/* User Profile */}
          <div className="p-4 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary font-semibold">
                {user?.username?.charAt(0) || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                  {user?.username || 'User'}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                  {user?.email || 'user@example.com'}
                </p>
              </div>
            </div>
            <button
              onClick={logout}
              className="w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors cursor-pointer"
            >
              退出登录
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className={`${sidebarOpen ? 'ml-64' : 'ml-0'} transition-all duration-300`}>
        {/* Top Bar */}
        <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-800/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between h-16 px-6">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 cursor-pointer"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <div className="flex items-center gap-4">
              {/* Global Search — S3-4 upgrade */}
              <div className="hidden md:block">
                <GlobalSearch />
              </div>

              <button className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 cursor-pointer relative">
                <svg className="w-6 h-6 text-slate-600 dark:text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
              </button>
              
              <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer text-sm font-medium">
                + 新建
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>

      {/* S3-1: live interface validation toast */}
      <ValidationToaster />
    </div>
  )
}

export default Layout
