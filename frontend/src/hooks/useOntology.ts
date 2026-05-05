import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import type {
  ObjectType,
  OntologyObject,
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
    mutationFn: async ({ id, tenantId }: { id: string; tenantId: string }) => {
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
        `${API_BASE_URL}/ontology/objects?type_id=${encodeURIComponent(typeId)}`,
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
    mutationFn: async (object: Partial<OntologyObject>) => {
      const response = await fetch(`${API_BASE_URL}/ontology/objects`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(object),
      })
      return handleResponse<OntologyObject>(response)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['objects', data.objectTypeId] })
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

export function useSearch() {
  const { token } = useAuth()
  return useMutation({
    mutationFn: async (query: {
      q: string
      tenantId?: string
      objectTypes?: string[]
    }) => {
      const response = await fetch(`${API_BASE_URL}/ontology/search`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify(query),
      })
      return handleResponse<OntologyObject[]>(response)
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
