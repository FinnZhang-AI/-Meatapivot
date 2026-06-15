export type PropertyType = 'string' | 'int' | 'float' | 'date' | 'boolean' | 'json'
export type Status = 'draft' | 'active' | 'archived'
export type CompileStatus = 'pending' | 'compiled' | 'error'
export type Cardinality = 'ONE_TO_ONE' | 'ONE_TO_MANY' | 'MANY_TO_ONE' | 'MANY_TO_MANY'
export type ExecutionType = 'direct' | 'function_backed' | 'workflow'

export interface PropertyValidation {
  regex?: string
  min?: number
  max?: number
  enum?: string[]
}

export interface PropertyDef {
  name: string
  displayName?: string
  type: PropertyType
  required?: boolean
  defaultValue?: any
  validation?: PropertyValidation
  linkTo?: string
}

export interface InterfaceLinkRequirement {
  name: string
  targetType: string
  cardinality: Cardinality
}

export interface ActionParameter {
  name: string
  displayName?: string
  type: string
  objectTypeRef?: string
  required?: boolean
  defaultValue?: any
  description?: string
}

export interface ActionRule {
  name: string
  ruleType: 'opa' | 'expression'
  policy: string
  description?: string
}

export interface CompileError {
  code: string
  message: string
  field?: string
}

export interface CompileResult {
  status: string
  errors: CompileError[]
  warnings: string[]
  neo4jConstraintsCreated: number
  durationMs: number
}

export interface ObjectType {
  id: string
  tenantId?: string
  name: string
  displayName?: string
  description?: string
  icon?: string
  properties: PropertyDef[]
  implementedInterfaces: string[]
  neo4jLabel?: string
  status: Status
  compileStatus: CompileStatus
  compileErrors?: CompileError[]
  version: number
  createdAt?: string
  updatedAt?: string
}

export interface OntologyObject {
  id: string
  tenantId?: string
  objectTypeId: string
  objectTypeName?: string
  objectKey: string
  properties: Record<string, any>
  neo4jNodeId?: string
  status: Status
  createdAt?: string
  updatedAt?: string
}

export interface LinkType {
  id: string
  tenantId?: string
  name: string
  displayName?: string
  description?: string
  sourceObjectTypeId: string
  sourceObjectTypeName?: string
  targetObjectTypeId: string
  targetObjectTypeName?: string
  cardinality: Cardinality
  neo4jEdgeType?: string
  properties?: PropertyDef[]
  status: Status
  version: number
  createdAt?: string
  updatedAt?: string
}

export interface OntologyLink {
  id: string
  tenantId?: string
  linkTypeId: string
  linkTypeName?: string
  sourceObjectId: string
  targetObjectId: string
  targetObjectKey?: string
  targetObjectType?: string
  properties?: Record<string, any>
  neo4jRelId?: string
  createdAt?: string
}

export interface InterfaceDef {
  id: string
  tenantId?: string
  name: string
  displayName?: string
  description?: string
  requiredProperties: PropertyDef[]
  requiredLinks: InterfaceLinkRequirement[]
  status: Status
  createdAt?: string
  updatedAt?: string
}

export interface ActionType {
  id: string
  tenantId?: string
  name: string
  displayName?: string
  description?: string
  targetObjectTypeId: string
  targetObjectTypeName?: string
  parameters: ActionParameter[]
  modifiesProperties?: string[]
  modifiesLinks?: string[]
  rules: ActionRule[]
  executionType: ExecutionType
  functionId?: string
  workflowId?: string
  status: Status
  createdAt?: string
  updatedAt?: string
}

export interface FunctionDef {
  id: string
  tenantId?: string
  name: string
  displayName?: string
  description?: string
  language: 'python' | 'typescript'
  code: string
  readOnly?: boolean
  timeoutSeconds: number
  memoryMb: number
  status: Status
  currentVersion?: number
  createdAt?: string
  updatedAt?: string
}

export interface GraphNode {
  id: string
  label: string
  objectType: string
  properties?: Record<string, any>
  x?: number
  y?: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
  properties?: Record<string, any>
}

export interface GraphMetadata {
  totalNodes: number
  totalEdges: number
  objectTypes: string[]
}

export interface SearchResultItem {
  objectId: string
  objectType: string
  objectKey: string
  label: string
  score: number
  source: string
  explanation?: string
  propertiesPreview: Record<string, any>
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
  total: number
  vectorHits: number
  graphHits: number
  reranked: boolean
  durationMs: number
}

export interface RecentAction {
  id: string
  actionName: string
  targetObjectKey: string
  status: string
  executedBy?: string
  executedAt?: string
  durationMs?: number
}

export interface DashboardStats {
  objectTypeCount: number
  objectInstanceCount: number
  linkTypeCount: number
  interfaceCount: number
  actionTypeCount: number
  functionCount: number
  actionExecutionCount: number
  recentActions: RecentAction[]
  objectTypeDistribution: ObjectTypeDistributionItem[]
}

export interface ObjectTypeDistributionItem {
  name: string
  instanceCount: number
}

export interface LLMUsageBucket {
  bucket: string
  callCount: number
  totalTokens: number
  estimatedCostCents: number
}

export interface LLMUsageTrend {
  groupBy: string
  hours: number
  buckets: LLMUsageBucket[]
}

export interface SubgraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  metadata: GraphMetadata
}
