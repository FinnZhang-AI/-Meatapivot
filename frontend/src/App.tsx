import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import KnowledgeGraph from './pages/KnowledgeGraph'
import Documents from './pages/Documents'
import DecisionFlow from './pages/DecisionFlow'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Login from './pages/Login'
import { AuthProvider } from './hooks/useAuth'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="knowledge-graph" element={<KnowledgeGraph />} />
          <Route path="documents" element={<Documents />} />
          <Route path="decision-flow" element={<DecisionFlow />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}

export default App