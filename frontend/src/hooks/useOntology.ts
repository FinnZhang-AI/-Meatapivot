import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import type {
  ObjectType,
  OntologyObject,
  OntologyLink,
  LinkType,
  InterfaceDef,
  ActionType,
  FunctionDef,
  SubgraphResponse,
} from '../types/ontology'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

function getAuthHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function useObjectTypes(tenantId: string) {
  const { token } = useAuth()
  return useQuery<ObjectType[]>({
    queryKey: ['objectTypes', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/object-types?tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<ObjectType[]>(response)
    },
    enabled: !!tenantId,
  })
}

export function useObjectType(id: string) {
  const { token } = useAuth()
  return useQuery<ObjectType>({
    queryKey: ['objectType', id],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/ontology/object-types/${id}`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<ObjectType>(response)
    },
    enabled: !!id,
  })
}

export function useCreateObjectType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (objectType: Partial<ObjectType>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/object-types`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(objectType),
      })
      return handleResponse<ObjectType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['objectTypes', data.tenantId] })
    },
  })
}

export function useUpdateObjectType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<ObjectType> }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/object-types/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<ObjectType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['objectTypes', data.tenantId] })
      queryClient.invalidateQueries({ queryKey: ['objectType', data.id] })
    },
  })
}

export function useDeleteObjectType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string; tenantId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/object-types/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['objectTypes', variables.tenantId] })
      queryClient.removeQueries({ queryKey: ['objectType', variables.id] })
    },
  })
}

export function useObjects(typeId: string) {
  const { token } = useAuth()
  return useQuery<OntologyObject[]>({
    queryKey: ['objects', typeId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/object-types/${encodeURIComponent(typeId)}/objects`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<OntologyObject[]>(response)
    },
    enabled: !!typeId,
  })
}

export function useCreateObject() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      objectTypeId,
      objectKey,
      properties,
    }: {
      objectTypeId: string
      objectKey: string
      properties?: Record<string, any>
    }) => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/object-types/${encodeURIComponent(objectTypeId)}/objects`,
        {
          method: 'POST',
          headers: getAuthHeaders(token),
          body: JSON.stringify({ objectKey, properties }),
        }
      )
      return handleResponse<OntologyObject>(response)
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['objects', variables.objectTypeId] })
    },
  })
}

export function useLinkTypes(tenantId: string) {
  const { token } = useAuth()
  return useQuery<LinkType[]>({
    queryKey: ['linkTypes', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/link-types?tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<LinkType[]>(response)
    },
    enabled: !!tenantId,
  })
}

export function useInterfaces(tenantId: string) {
  const { token } = useAuth()
  return useQuery<InterfaceDef[]>({
    queryKey: ['interfaces', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/interfaces?tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<InterfaceDef[]>(response)
    },
    enabled: !!tenantId,
  })
}

export function useActionTypes(tenantId: string) {
  const { token } = useAuth()
  return useQuery<ActionType[]>({
    queryKey: ['actionTypes', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/action-types?tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<ActionType[]>(response)
    },
    enabled: !!tenantId,
  })
}

export function useFunctions(tenantId: string) {
  const { token } = useAuth()
  return useQuery<FunctionDef[]>({
    queryKey: ['functions', tenantId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/functions?tenant_id=${encodeURIComponent(tenantId)}`,
        { headers: getAuthHeaders(token) }
      )
      return handleResponse<FunctionDef[]>(response)
    },
    enabled: !!tenantId,
  })
}

// Search
export interface SearchResponse {
  query: string
  results: OntologyObject[]
  total: number
  vector_hits: number
  graph_hits: number
  reranked: boolean
  duration_ms: number
}

export function useSearch() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (query: {
      q: string
      tenantId?: string
      objectTypes?: string[]
      searchMode?: string
    }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/search`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({
          query: query.q,
          tenant_id: query.tenantId,
          object_types: query.objectTypes,
          search_mode: query.searchMode || 'hybrid',
        }),
      })
      return handleResponse<SearchResponse>(response)
    },
  })
}

// Single object + links
export function useObject(objectId: string) {
  const { token } = useAuth()
  return useQuery<OntologyObject>({
    queryKey: ['object', objectId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/ontology/objects/${objectId}`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<OntologyObject>(response)
    },
    enabled: !!objectId,
  })
}

export function useObjectLinks(objectId: string) {
  const { token } = useAuth()
  return useQuery<OntologyLink[]>({
    queryKey: ['objectLinks', objectId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/ontology/objects/${objectId}/links`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<OntologyLink[]>(response)
    },
    enabled: !!objectId,
  })
}

export function useExecuteAction() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      actionTypeId,
      targetObjectId,
      parameters,
    }: {
      actionTypeId: string
      targetObjectId: string
      parameters?: Record<string, any>
    }) => {
      const response = await fetch(
        `${API_BASE_URL}/ontology/action-types/${actionTypeId}/execute`,
        {
          method: 'POST',
          headers: getAuthHeaders(token),
          body: JSON.stringify({ target_object_id: targetObjectId, parameters }),
        }
      )
      return handleResponse<{ success: boolean; message?: string }>(response)
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['object', variables.targetObjectId] })
    },
  })
}

export function useUpdateObject() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      objectId,
      properties,
    }: {
      objectId: string
      properties: Record<string, any>
    }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/objects/${objectId}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify({ properties }),
      })
      return handleResponse<OntologyObject>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['object', data.id] })
      queryClient.invalidateQueries({ queryKey: ['objects'] })
    },
  })
}

export function useCreateLink() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      linkTypeId,
      sourceObjectId,
      targetObjectId,
      properties,
    }: {
      linkTypeId: string
      sourceObjectId: string
      targetObjectId: string
      properties?: Record<string, any>
    }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/link-types/${linkTypeId}/links`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({ source_object_id: sourceObjectId, target_object_id: targetObjectId, properties }),
      })
      return handleResponse<OntologyLink>(response)
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['objectLinks', variables.sourceObjectId] })
      queryClient.invalidateQueries({ queryKey: ['objectLinks', variables.targetObjectId] })
    },
  })
}

export function useDeleteLink() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ linkId, objectId: _objectId }: { linkId: string; objectId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/links/${linkId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['objectLinks', variables.objectId] })
    },
  })
}

export function useSubgraph(objectId: string) {
  const { token } = useAuth()
  return useQuery<SubgraphResponse>({
    queryKey: ['subgraph', objectId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/ontology/subgraph/${objectId}`, {
        headers: getAuthHeaders(token),
      })
      return handleResponse<SubgraphResponse>(response)
    },
    enabled: !!objectId,
  })
}

// LinkType CRUD
export function useCreateLinkType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (linkType: Partial<LinkType>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/link-types`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(linkType),
      })
      return handleResponse<LinkType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['linkTypes', data.tenantId] })
    },
  })
}

export function useUpdateLinkType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<LinkType> }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/link-types/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<LinkType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['linkTypes', data.tenantId] })
    },
  })
}

export function useDeleteLinkType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string; tenantId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/link-types/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['linkTypes', variables.tenantId] })
    },
  })
}

// Interface CRUD
export function useCreateInterface() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (iface: Partial<InterfaceDef>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/interfaces`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(iface),
      })
      return handleResponse<InterfaceDef>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['interfaces', data.tenantId] })
    },
  })
}

export function useUpdateInterface() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<InterfaceDef> }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/interfaces/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<InterfaceDef>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['interfaces', data.tenantId] })
    },
  })
}

export function useDeleteInterface() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string; tenantId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/interfaces/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['interfaces', variables.tenantId] })
    },
  })
}

// ActionType CRUD
export function useCreateActionType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (actionType: Partial<ActionType>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/action-types`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(actionType),
      })
      return handleResponse<ActionType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['actionTypes', data.tenantId] })
    },
  })
}

export function useUpdateActionType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<ActionType> }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/action-types/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<ActionType>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['actionTypes', data.tenantId] })
    },
  })
}

export function useDeleteActionType() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string; tenantId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/action-types/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['actionTypes', variables.tenantId] })
    },
  })
}

// Function CRUD
export function useCreateFunction() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (fn: Partial<FunctionDef>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/functions`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(fn),
      })
      return handleResponse<FunctionDef>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['functions', data.tenantId] })
    },
  })
}

export function useUpdateFunction() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<FunctionDef> }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/functions/${id}`, {
        method: 'PUT',
        headers: getAuthHeaders(token),
        body: JSON.stringify(data),
      })
      return handleResponse<FunctionDef>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['functions', data.tenantId] })
    },
  })
}

export function useDeleteFunction() {
  const { token } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id }: { id: string; tenantId: string }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/functions/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(token),
      })
      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP ${response.status}`)
      }
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['functions', variables.tenantId] })
    },
  })
}
