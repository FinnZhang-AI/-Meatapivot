import { useState } from 'react'

const Settings = () => {
  const [activeTab, setActiveTab] = useState('general')

  const settings = {
    general: {
      appName: 'Knowledge Platform',
      language: 'zh-CN',
      timezone: 'Asia/Shanghai',
      theme: 'dark',
    },
    database: {
      postgresHost: 'localhost',
      postgresPort: '5432',
      neo4jUri: 'bolt://localhost:7687',
      rabbitmqUrl: 'amqp://localhost:5672',
    },
    security: {
      jwtExpiry: '24h',
      maxLoginAttempts: '5',
      sessionTimeout: '30min',
      twoFactorAuth: false,
    },
  }

  const tabs = [
    { id: 'general', label: '通用设置', icon: '⚙️' },
    { id: 'database', label: '数据库配置', icon: '🗄️' },
    { id: 'security', label: '安全设置', icon: '🔒' },
    { id: 'users', label: '用户管理', icon: '👥' },
    { id: 'logs', label: '系统日志', icon: '📋' },
  ]

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
          系统设置
        </h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          管理平台配置、安全策略与用户权限
        </p>
      </div>

      {/* Settings Tabs */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-4 text-sm font-medium whitespace-nowrap transition-colors cursor-pointer ${
                activeTab === tab.id
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'general' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  基本配置
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      应用名称
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.general.appName}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      语言
                    </label>
                    <select
                      defaultValue={settings.general.language}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none cursor-pointer"
                    >
                      <option value="zh-CN">简体中文</option>
                      <option value="en-US">English</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      时区
                    </label>
                    <select
                      defaultValue={settings.general.timezone}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none cursor-pointer"
                    >
                      <option value="Asia/Shanghai">中国标准时间 (UTC+8)</option>
                      <option value="America/New_York">美国东部时间 (UTC-5)</option>
                      <option value="Europe/London">格林威治标准时间 (UTC+0)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      主题
                    </label>
                    <select
                      defaultValue={settings.general.theme}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none cursor-pointer"
                    >
                      <option value="light">浅色</option>
                      <option value="dark">深色</option>
                      <option value="auto">自动</option>
                    </select>
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-6 border-t border-slate-200 dark:border-slate-700">
                <button className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  取消
                </button>
                <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer">
                  保存设置
                </button>
              </div>
            </div>
          )}

          {activeTab === 'database' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  数据库连接配置
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      PostgreSQL 主机
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.database.postgresHost}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      PostgreSQL 端口
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.database.postgresPort}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Neo4j URI
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.database.neo4jUri}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      RabbitMQ URL
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.database.rabbitmqUrl}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-6 border-t border-slate-200 dark:border-slate-700">
                <button className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  测试连接
                </button>
                <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer">
                  保存配置
                </button>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  安全策略配置
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      JWT Token 过期时间
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.security.jwtExpiry}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      最大登录尝试次数
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.security.maxLoginAttempts}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      会话超时时间
                    </label>
                    <input
                      type="text"
                      defaultValue={settings.security.sessionTimeout}
                      className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                    />
                  </div>
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      defaultChecked={settings.security.twoFactorAuth}
                      className="w-4 h-4 text-primary border-slate-300 rounded focus:ring-primary cursor-pointer"
                    />
                    <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      启用双因素认证
                    </label>
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-6 border-t border-slate-200 dark:border-slate-700">
                <button className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  取消
                </button>
                <button className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600 transition-colors cursor-pointer">
                  保存设置
                </button>
              </div>
            </div>
          )}

          {activeTab === 'users' && (
            <div className="text-center py-12">
              <svg className="w-16 h-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                用户管理功能开发中
              </h3>
              <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                包含用户列表、角色分配、权限管理等功能即将上线
              </p>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="text-center py-12">
              <svg className="w-16 h-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                系统日志功能开发中
              </h3>
              <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                包含操作日志、审计日志、错误日志查询等功能即将上线
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Settings