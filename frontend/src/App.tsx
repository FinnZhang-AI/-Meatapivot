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

// Ontology Pages
import ObjectTypeList from './pages/ontology/ObjectTypeList'
import ObjectTypeDetail from './pages/ontology/ObjectTypeDetail'
import LinkTypeList from './pages/ontology/LinkTypeList'
import InterfaceList from './pages/ontology/InterfaceList'
import ActionTypeList from './pages/ontology/ActionTypeList'
import FunctionList from './pages/ontology/FunctionList'
import SemanticSearch from './pages/ontology/SemanticSearch'

// Object View
import ObjectView from './pages/objects/ObjectView'

// AIP Pages
import Chat from './pages/aip/Chat'
import RAGSearch from './pages/aip/RAGSearch'
import AgentChat from './pages/aip/AgentChat'
import PromptManager from './pages/aip/PromptManager'

// Workshop Pages
import WorkshopList from './pages/workshop/WorkshopList'
import WorkshopEditor from './pages/workshop/WorkshopEditor'

// LLM Cost Dashboard (S4-1)
import CostDashboard from './pages/aip/CostDashboard'

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

          {/* Ontology Routes */}
          <Route path="ontology/object-types" element={<ObjectTypeList />} />
          <Route path="ontology/object-types/:id" element={<ObjectTypeDetail />} />
          <Route path="ontology/link-types" element={<LinkTypeList />} />
          <Route path="ontology/interfaces" element={<InterfaceList />} />
          <Route path="ontology/action-types" element={<ActionTypeList />} />
          <Route path="ontology/functions" element={<FunctionList />} />
          <Route path="ontology/search" element={<SemanticSearch />} />

          {/* Object View */}
          <Route path="objects/:type/:id" element={<ObjectView />} />

          {/* AIP Routes */}
          <Route path="aip/chat" element={<Chat />} />
          <Route path="aip/rag" element={<RAGSearch />} />
          <Route path="aip/agents" element={<AgentChat />} />
          <Route path="aip/prompts" element={<PromptManager />} />

          {/* Workshop Routes (S3-3) */}
          <Route path="workshop" element={<WorkshopList />} />
          <Route path="workshop/editor/:appId" element={<WorkshopEditor />} />

          {/* LLM Cost Dashboard (S4-1) */}
          <Route path="aip/cost" element={<CostDashboard />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}

export default App
