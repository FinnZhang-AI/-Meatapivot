# Meatapivot 前端组件设计文档

> 基于 PRD v2.0 的 Apps 应用层需求，设计前端组件架构、页面结构与状态管理方案。
> 
> **技术栈**：React 18 + TypeScript + Vite + TailwindCSS + TanStack Query + Zustand + XYFlow + React Force Graph

---

## 1. 组件架构总览

```
src/
├── components/              # 原子/分子组件
│   ├── ui/                  # 基础 UI (shadcn/ui style)
│   ├── ontology/            # Ontology 专用组件
│   ├── aip/                 # AIP 专用组件
│   ├── layout/              # 布局组件
│   └── charts/              # 图表组件
├── pages/                   # 页面级组件
│   ├── ontology/            # Ontology 管理页
│   ├── objects/             # Object View 页
│   ├── workshop/            # 应用构建器
│   ├── aip/                 # AI 对话/搜索页
│   └── dashboard/           # 仪表盘
├── hooks/                   # 自定义 Hooks
│   ├── useOntology.ts       # Ontology 数据操作
│   ├── useAIP.ts            # AIP 数据操作
│   ├── useAuth.ts           # 认证 (existing)
│   └── useWebSocket.ts      # WebSocket 连接
├── stores/                  # Zustand 状态管理
│   ├── ontologyStore.ts     # Ontology 全局状态
│   ├── aipStore.ts          # AIP 全局状态
│   └── appStore.ts          # 应用级状态
├── types/                   # TypeScript 类型定义
│   ├── ontology.ts
│   └── aip.ts
└── lib/                     # 工具函数
    ├── api.ts               # Axios/Fetch 封装
    ├── utils.ts
    └── constants.ts
```

---

## 2. 组件清单

### 2.1 基础 UI 组件 (`components/ui/`)

| 组件 | 来源 | 说明 |
|:-----|:-----|:-----|
| Button | 自研 | 支持 variant: primary / secondary / ghost / danger / link |
| Input | 自研 | 支持 prefix/suffix, error state, clearable |
| Select | 自研 | 支持单选/多选/搜索/异步加载 |
| Dialog | 自研 | 支持 header/footer/sizes, ESC 关闭 |
| Table | 自研 | 支持排序/筛选/分页/行选择/空状态 |
| Form | 自研 | 基于 react-hook-form 封装，支持 schema 校验 (zod) |
| Tabs | 自研 | 支持路由级 Tab |
| Badge | 自研 | 状态标签 |
| Tooltip | 自研 | 文字提示 |
| Skeleton | 自研 | 加载占位 |
| EmptyState | 自研 | 空状态插图 + 文案 + 操作按钮 |
| LoadingOverlay | 自研 | 全局/局部加载遮罩 |
| Toast | 自研 | 消息通知 (成功/错误/警告/信息) |
| ConfirmModal | 自研 | 确认弹窗 |

### 2.2 Ontology 专用组件 (`components/ontology/`)

#### ObjectTypeCard
```typescript
interface ObjectTypeCardProps {
  objectType: ObjectType;
  onEdit?: (id: string) => void;
  onCompile?: (id: string) => void;
  onDelete?: (id: string) => void;
  compact?: boolean;  // 紧凑模式用于列表
}
```
- **视觉**：图标 + 名称 + 状态徽章 + 属性数量 + 操作按钮
- **交互**：hover 显示快捷操作，点击展开详情抽屉

#### PropertyTable
```typescript
interface PropertyTableProps {
  properties: PropertyDef[];
  values?: Record<string, any>;      // 当前值（Object View 模式）
  editable?: boolean;
  onChange?: (name: string, value: any) => void;
  onValidate?: (errors: Record<string, string>) => void;
}
```
- **视觉**：两列布局（属性名 + 值），值按类型渲染不同输入控件
- **交互**：编辑模式 inline editing，失焦自动保存（乐观更新）

#### PropertyEditor
```typescript
interface PropertyEditorProps {
  property: PropertyDef;
  value: any;
  onChange: (value: any) => void;
  error?: string;
}
```
- **渲染映射**：
  - `string` → Input
  - `int/float` → InputNumber
  - `date` → DatePicker
  - `boolean` → Switch
  - `json` → CodeEditor ( Monaco / CodeMirror )
  - `object_ref` → Select (异步加载目标类型对象)

#### RelatedObjects
```typescript
interface RelatedObjectsProps {
  objectId: string;
  objectType: string;
  depth?: number;
  onNavigate?: (objectId: string, objectType: string) => void;
  onAddRelation?: (linkTypeId: string) => void;
  onRemoveRelation?: (linkId: string) => void;
}
```
- **视觉**：按 Link Type 分组的折叠面板
- **交互**：展开动画，点击对象卡片跳转，hover 显示删除按钮

#### RelatedObjectCard
```typescript
interface RelatedObjectCardProps {
  object: OntologyObject;
  linkType: string;
  direction: 'outgoing' | 'incoming';
  onClick?: () => void;
}
```
- **视觉**：小卡片，显示对象图标 + 主键 + 类型标签

#### ActionButton
```typescript
interface ActionButtonProps {
  action: ActionType;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  onExecute?: (params: Record<string, any>) => void;
}
```
- **视觉**：按钮，带图标，tooltip 显示描述
- **交互**：点击打开 ActionDialog

#### ActionDialog
```typescript
interface ActionDialogProps {
  action: ActionType;
  targetObjectId?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (result: ActionResult) => void;
}
```
- **视觉**：Dialog，内含动态生成的表单
- **表单生成**：根据 `action.parameters` 映射为 Form 字段
- **执行状态**：表单 → 校验 → 提交 → loading → 结果展示

#### ActionResultView
```typescript
interface ActionResultViewProps {
  result: ActionResult;
  onClose?: () => void;
  onRetry?: () => void;
}
```
- **视觉**：成功/失败状态动画，展示结果摘要或错误详情

#### CompileStatusBadge
```typescript
interface CompileStatusBadgeProps {
  status: 'pending' | 'compiled' | 'error' | 'running';
  errorCount?: number;
}
```
- **视觉**：带动画的徽章，error 时显示数字角标

#### CompileLogViewer
```typescript
interface CompileLogViewerProps {
  logs: CompileLog[];
  onRecompile?: () => void;
}
```
- **视觉**：时间线布局，成功绿色 / 警告黄色 / 错误红色

#### OntologyGraph
```typescript
interface OntologyGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerNodeId?: string;
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  height?: number;
  readonly?: boolean;
}
```
- **技术**：`react-force-graph-2d` 或 `react-force-graph-3d`
- **视觉**：力导向图，节点按 Object Type 着色，边带标签
- **交互**：拖拽、缩放、点击高亮、hover 显示 tooltip

#### InterfaceValidator
```typescript
interface InterfaceValidatorProps {
  interfaceId: string;
  onValidate?: (result: ValidationResult) => void;
}
```
- **视觉**：进度条 + 结果列表（通过/失败）

### 2.3 AIP 专用组件 (`components/aip/`)

#### ChatInterface
```typescript
interface ChatInterfaceProps {
  sessionId?: string;
  modelId?: string;
  onModelChange?: (modelId: string) => void;
  tools?: ToolDef[];
}
```
- **视觉**：类 ChatGPT 布局，左侧会话列表，右侧对话区
- **交互**：
  - 输入框支持 Markdown 预览
  - 流式输出（SSE）逐字显示
  - 代码块语法高亮 + 复制按钮
  - 消息可重新生成/编辑/删除

#### ChatMessageBubble
```typescript
interface ChatMessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  onRegenerate?: () => void;
  onEdit?: (content: string) => void;
}
```
- **视觉**：用户右对齐，助手左对齐，不同背景色
- **交互**：hover 显示操作栏（复制/重新生成/编辑）

#### ModelSelector
```typescript
interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  models: ModelOption[];
}

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  description?: string;
  costPer1kTokens?: number;
}
```
- **视觉**：下拉选择，显示模型图标 + 名称 + 提供商

#### RAGSearchPanel
```typescript
interface RAGSearchPanelProps {
  onSearch: (query: string) => void;
  results?: RAGResult[];
  loading?: boolean;
}
```
- **视觉**：搜索框 + 结果列表 + 来源侧边栏
- **交互**：结果卡片展开显示引用来源，点击跳转

#### RAGAnswerCard
```typescript
interface RAGAnswerCardProps {
  answer: string;
  sources: RAGSource[];
  entities: DetectedEntity[];
  onSourceClick?: (source: RAGSource) => void;
  onEntityClick?: (entity: DetectedEntity) => void;
}
```
- **视觉**：答案文本 + 引用上标 + 来源卡片列表
- **交互**：点击引用上标滚动到对应来源

#### AgentStepViewer
```typescript
interface AgentStepViewerProps {
  steps: AgentStep[];
  currentStepIndex: number;
  onInterrupt?: () => void;
  onResume?: (input: string) => void;
  onCancel?: () => void;
}
```
- **视觉**：垂直时间线，每步展示 Thought/Action/Observation
- **交互**：Human-in-the-loop 时显示输入框 + 继续/取消按钮

#### GuardrailsIndicator
```typescript
interface GuardrailsIndicatorProps {
  checks: GuardrailsCheck[];
}
```
- **视觉**：小盾牌图标，绿色/黄色/红色状态，hover 显示详情

### 2.4 Workshop 应用构建器组件 (`components/workshop/`)

#### ComponentPalette
```typescript
interface ComponentPaletteProps {
  components: WorkshopComponentDef[];
  onDragStart: (component: WorkshopComponentDef) => void;
}
```
- **视觉**：左侧侧边栏，分类展示可拖拽组件（Object Table / Filter / Chart / Action Button / Link Navigator）
- **交互**：拖拽时显示 ghost 预览

#### WorkshopCanvas
```typescript
interface WorkshopCanvasProps {
  nodes: WorkshopNode[];
  edges: WorkshopEdge[];
  onNodesChange: (nodes: WorkshopNode[]) => void;
  onEdgesChange: (edges: WorkshopEdge[]) => void;
  onNodeSelect: (node: WorkshopNode) => void;
  onContextMenu?: (event: React.MouseEvent, node?: WorkshopNode) => void;
}
```
- **技术**：`@xyflow/react`
- **视觉**：无限画布，网格背景，节点可拖拽连接
- **交互**：拖拽组件面板 → 画布生成节点，节点间可连线传递数据

#### PropertyPanel
```typescript
interface PropertyPanelProps {
  selectedNode: WorkshopNode | null;
  objectTypes: ObjectType[];
  onChange: (nodeId: string, props: Record<string, any>) => void;
}
```
- **视觉**：右侧属性面板，根据选中节点类型动态渲染配置表单
- **交互**：配置变更实时影响画布中的节点预览

#### PreviewMode
```typescript
interface PreviewModeProps {
  appConfig: WorkshopAppConfig;
  onInteract?: (event: AppInteractionEvent) => void;
}
```
- **视觉**：隐藏编辑器 UI，仅展示构建的应用界面
- **交互**：Filter 变更 → Table 刷新 → Chart 重绘（数据联动）

### 2.5 布局组件 (`components/layout/`)

| 组件 | 说明 |
|:-----|:-----|
| Sidebar | 侧边导航，支持折叠，权限控制菜单项可见性 |
| TopBar | 顶部栏，面包屑、全局搜索、用户头像、租户切换 |
| Breadcrumb | 面包屑导航，支持动态路由解析 |
| TenantSwitcher | 租户切换下拉（admin 可见） |
| GlobalSearch | 全局搜索框，支持模式切换（Keyword/Semantic/RAG） |
| NotificationBell | 通知铃铛，WebSocket 推送消息 |

---

## 3. 页面设计

### 3.1 Ontology 管理后台 (`/ontology/*`)

#### `/ontology/object-types`
- **布局**：Table 列表 + 顶部操作栏（创建/导入/编译全部）
- **列**：图标 | 名称 | 显示名 | 属性数 | 状态 | 编译状态 | 操作
- **交互**：
  - 行点击 → 右侧抽屉展开详情
  - 批量选择 → 批量编译/导出
  - 搜索框实时过滤

#### `/ontology/object-types/:id`
- **布局**：Tab 页（Overview | Properties | Links | Actions | History）
- **Overview**：基本信息卡片 + 编译状态 + 统计
- **Properties**：PropertyTable 编辑模式
- **Links**：出/入关系类型列表
- **Actions**：绑定的 Action 列表
- **History**：版本变更记录

#### `/ontology/link-types`
- **布局**：Table 列表，列：名称 | 源类型 | 目标类型 | 基数 | 状态
- **交互**：可视化展示类型间关系（小型力导向图）

#### `/ontology/interfaces`
- **布局**：Table + 校验按钮
- **交互**：点击校验 → 弹窗展示所有实现者的校验结果

#### `/ontology/actions`
- **布局**：Table + 测试执行抽屉
- **交互**：选择 Action → 弹出参数表单 → 执行 → 查看结果

#### `/ontology/functions`
- **布局**：Table + 代码编辑器
- **交互**：内嵌 Monaco Editor，支持语法高亮、测试运行

### 3.2 Object View 页面 (`/objects/:type/:id`)

```
┌─────────────────────────────────────────────────────────────┐
│  🔙 返回      Employee / 张三                    [编辑] [⋮] │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Properties                          │ Related      │   │
│  │  ┌──────────────────────────────────┤ Objects      │   │
│  │  │ 姓名        张三                  │ ┌──────────┐ │   │
│  │  │ 部门        工程部  →            │ │ belongs_to│ │   │
│  │  │ 邮箱        zs@company.com       │ │ 工程部    │ │   │
│  │  │ 入职日期    2024-01-15           │ │ manages   │ │   │
│  │  │ 状态        ● Active             │ │ 后端组    │ │   │
│  │  └──────────────────────────────────┘ │ reports_to│ │   │
│  │                                       │ 李四      │ │   │
│  │  [变更部门] [调整薪资] [离职]         └──────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  关系图谱 (2 跳)                                     │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │         ○ 张三                                  │ │   │
│  │  │        / | \                                    │ │   │
│  │  │    ○工程部 ○后端组 ○李四                       │ │   │
│  │  │       |            |                            │ │   │
│  │  │    ○研发中心    ○王五                          │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

- **加载策略**：并行请求 properties + related_objects + available_actions + subgraph
- **状态管理**：本地编辑状态 → 批量保存 / 取消

### 3.3 Workshop 构建器 (`/workshop/builder/:appId?`)

```
┌─────────────────────────────────────────────────────────────┐
│  🏗️ App Builder              [预览] [保存] [发布]           │
├──────────┬────────────────────────────────────┬─────────────┤
│ 组件面板  │         画布区域                    │ 属性面板    │
│          │                                    │             │
│ 📁 Object│    ┌─────────┐      ┌─────────┐   │ 选中:      │
│   ├─Table│    │ Filter  │─────▶│ Table   │   │ ObjectTable │
│   ├─Chart│    └─────────┘      └─────────┘   │             │
│   └─View │           │              │         │ ObjectType: │
│          │           ▼              ▼         │ [Employee ▼]│
│ 🔧 Action│    ┌─────────────────────────┐    │ Columns:    │
│   ├─Button    │        Chart            │    │ [☑] 姓名    │
│   └─Form │    └─────────────────────────┘    │ [☑] 部门    │
│          │                                    │ [ ] 邮箱    │
│ 🔗 Link  │                                    │             │
│   ├─Nav  │                                    │ Filter:     │
│   └─Tree │                                    │ [☑] 启用    │
│          │                                    │ 条件:       │
│          │                                    │ 部门 = 工程部│
└──────────┴────────────────────────────────────┴─────────────┘
```

- **画布节点类型**：
  - `filterNode`：过滤条件配置
  - `tableNode`：对象表格展示
  - `chartNode`：图表（bar/line/pie）
  - `actionNode`：Action 按钮组
  - `detailNode`：对象详情卡片
  - `linkNavNode`：关联导航

- **数据流**：
  - 边连接表示数据传递
  - FilterNode 输出 → TableNode 输入（查询参数）
  - TableNode 选择行 → DetailNode 输入（对象 ID）
  - TableNode 聚合数据 → ChartNode 输入（图表数据）

### 3.4 AI 对话页面 (`/aip/chat`)

```
┌─────────────────────────────────────────────────────────────┐
│  🤖 AI Assistant                    [模型: GPT-4 ▼]        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │  今天有什么可以帮您的？                                │   │
│  │                                                      │   │
│  │  🤖 您好！我是 Meatapivot AI 助手。我可以帮您：        │   │
│  │     • 查询知识图谱中的实体信息                         │   │
│  │     • 分析文档内容                                     │   │
│  │     • 执行决策流程                                     │   │
│  │                                                      │   │
│  │  👤 工程部有多少人？                                   │   │
│  │                                                      │   │
│  │  🤖 根据知识图谱查询，工程部目前有 23 名员工。         │   │
│  │     来源: [1] Ontology:Employee [2] Ontology:Department│   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [搜索知识库...]  [发送]                             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.5 仪表盘首页 (`/dashboard`)

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Dashboard                              [刷新] [设置]    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │ Object   │ │ Action   │ │ LLM      │ │ Avg      │     │
│  │ Types: 15│ │ Execs:128│ │ Calls:45│ │ Latency  │     │
│  │ ↑ 3      │ │ ↑ 12%    │ │ ↑ 20%   │ │ 234ms ↓  │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│  ┌─────────────────────────┐ ┌─────────────────────────┐  │
│  │  Ontology 实例增长趋势    │ │  LLM 成本趋势 (7天)      │  │
│  │  [Recharts AreaChart]   │ │  [Recharts BarChart]    │  │
│  └─────────────────────────┘ └─────────────────────────┘  │
│  ┌─────────────────────────┐ ┌─────────────────────────┐  │
│  │  最近 Action 执行记录     │ │  热门搜索词              │  │
│  │  [Table]                │ │  [WordCloud / TagCloud] │  │
│  └─────────────────────────┘ └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 状态管理设计

### 4.1 Zustand Store 结构

```typescript
// stores/ontologyStore.ts
interface OntologyState {
  // Object Types
  objectTypes: ObjectType[];
  objectTypesLoading: boolean;
  selectedObjectType: ObjectType | null;
  
  // Object Instances
  objects: Record<string, OntologyObject>;  // key = type:id
  objectsLoading: Record<string, boolean>;
  
  // Graph Data
  subgraph: SubgraphResponse | null;
  subgraphLoading: boolean;
  
  // Actions
  availableActions: ActionType[];
  actionExecuting: Record<string, boolean>;  // key = actionId
  
  // Compile
  compileProgress: CompileProgress | null;
  
  // Actions
  fetchObjectTypes: (params?: PaginationParams) => Promise<void>;
  fetchObject: (type: string, id: string) => Promise<void>;
  fetchSubgraph: (objectId: string, depth?: number) => Promise<void>;
  executeAction: (actionId: string, params: any) => Promise<ActionResult>;
  updateObjectProperty: (type: string, id: string, name: string, value: any) => Promise<void>;
}

// stores/aipStore.ts
interface AIPState {
  // Chat
  messages: ChatMessage[];
  chatLoading: boolean;
  streamingContent: string;
  
  // RAG
  ragResults: RAGResult | null;
  ragLoading: boolean;
  
  // Agent
  agentSession: AgentSession | null;
  agentSteps: AgentStep[];
  agentLoading: boolean;
  
  // Config
  selectedModel: string;
  availableModels: ModelOption[];
  
  // Actions
  sendMessage: (content: string, stream?: boolean) => Promise<void>;
  sendRAGQuery: (query: string) => Promise<void>;
  runAgent: (agentId: string, input: string) => Promise<void>;
  interruptAgent: (sessionId: string, action: string, input?: string) => Promise<void>;
}
```

### 4.2 TanStack Query Keys

```typescript
// 查询键规范
export const queryKeys = {
  ontology: {
    objectTypes: (params: PaginationParams) => ['ontology', 'object-types', params],
    objectType: (id: string) => ['ontology', 'object-types', id],
    object: (type: string, id: string) => ['ontology', 'objects', type, id],
    subgraph: (id: string, depth: number) => ['ontology', 'subgraph', id, depth],
    linkTypes: () => ['ontology', 'link-types'],
    interfaces: () => ['ontology', 'interfaces'],
    actions: (objectTypeId?: string) => ['ontology', 'actions', objectTypeId],
    functions: () => ['ontology', 'functions'],
    search: (query: string, mode: string) => ['ontology', 'search', query, mode],
  },
  aip: {
    chat: (sessionId: string) => ['aip', 'chat', sessionId],
    rag: (query: string) => ['aip', 'rag', query],
    agent: (sessionId: string) => ['aip', 'agent', sessionId],
    models: () => ['aip', 'models'],
  },
  dashboard: {
    stats: () => ['dashboard', 'stats'],
    activities: () => ['dashboard', 'activities'],
    trends: (period: string) => ['dashboard', 'trends', period],
  },
};
```

---

## 5. 路由设计

```typescript
// App.tsx 路由表
const routes = [
  // 认证
  { path: '/login', element: <LoginPage /> },
  
  // 主布局
  {
    element: <MainLayout />,
    children: [
      // 仪表盘
      { path: '/', element: <DashboardPage /> },
      { path: '/dashboard', element: <DashboardPage /> },
      
      // Ontology 管理
      { path: '/ontology/object-types', element: <ObjectTypeListPage /> },
      { path: '/ontology/object-types/:id', element: <ObjectTypeDetailPage /> },
      { path: '/ontology/link-types', element: <LinkTypeListPage /> },
      { path: '/ontology/interfaces', element: <InterfaceListPage /> },
      { path: '/ontology/actions', element: <ActionTypeListPage /> },
      { path: '/ontology/functions', element: <FunctionListPage /> },
      
      // Object View
      { path: '/objects/:type/:id', element: <ObjectViewPage /> },
      
      // Workshop
      { path: '/workshop', element: <WorkshopAppListPage /> },
      { path: '/workshop/builder/:appId?', element: <WorkshopBuilderPage /> },
      { path: '/workshop/apps/:appId', element: <WorkshopAppRuntimePage /> },
      
      // AIP
      { path: '/aip/chat', element: <ChatPage /> },
      { path: '/aip/rag', element: <RAGSearchPage /> },
      { path: '/aip/agents', element: <AgentListPage /> },
      { path: '/aip/agents/:id', element: <AgentDetailPage /> },
      
      // 文档
      { path: '/documents', element: <DocumentsPage /> },
      
      // 设置
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
];
```

---

## 6. 性能优化策略

| 策略 | 应用场景 | 实现方式 |
|:-----|:---------|:---------|
| 虚拟列表 | Object Table（千行以上） | `react-window` 或 `@tanstack/react-virtual` |
| 防抖搜索 | 全局搜索 / 属性过滤 | `lodash.debounce` 300ms |
| 增量加载 | 子图可视化（大量节点） | 先加载中心节点 + 1 跳，懒加载扩展 |
| 乐观更新 | 属性编辑 / Action 执行 | TanStack Query `optimisticUpdate` |
| 代码分割 | Workshop Builder / Chat | React.lazy + Suspense |
| 资源预加载 | Object View 关联对象 | hover 时预加载目标对象数据 |
| WebSocket 复用 | 编译进度 / Agent 执行 | 单一连接，按 event 类型分发 |
| 图表防抖 | Workshop Chart 重绘 | `useDeferredValue` + `React.memo` |

---

## 7. 可访问性 (a11y) 要求

- 所有交互组件支持键盘导航（Tab / Enter / Escape）
- 图标按钮必须有 `aria-label`
- 表单字段必须有 `label` 关联
- 颜色对比度 ≥ WCAG AA 标准（4.5:1）
- 加载状态必须告知屏幕阅读器（`aria-live`）
- 错误信息必须关联到对应输入框（`aria-describedby`）

---

## 8. 组件开发规范

```typescript
// 每个组件文件结构
// components/ontology/PropertyTable.tsx

// 1. 导入
import React from 'react';
import { useOntologyStore } from '@/stores/ontologyStore';

// 2. 类型定义
interface PropertyTableProps {
  properties: PropertyDef[];
  values?: Record<string, any>;
  editable?: boolean;
}

// 3. 组件实现
export const PropertyTable: React.FC<PropertyTableProps> = ({
  properties,
  values,
  editable = false,
}) => {
  // 状态与逻辑
  
  // 渲染
  return (
    <div className="space-y-2">
      {/* ... */}
    </div>
  );
};

// 4. 默认导出
export default PropertyTable;
```

**命名规范**：
- 组件：PascalCase，如 `PropertyTable`
- Hooks：camelCase，前缀 `use`，如 `useOntology`
- Stores：camelCase，后缀 `Store`，如 `ontologyStore`
- 类型：PascalCase，如 `PropertyDef`
- 常量：UPPER_SNAKE_CASE

---

> **版本历史**：
> - v2.0 (2026-05-04): 基于 PRD v2.0 创建，覆盖 Ontology / AIP / Workshop / Dashboard 全部前端组件
