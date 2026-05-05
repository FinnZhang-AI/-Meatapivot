import { create } from 'zustand'
import {
  ObjectType,
  LinkType,
  InterfaceDef,
  ActionType,
  FunctionDef,
  OntologyObject,
} from '../types/ontology'

interface OntologyState {
  objectTypes: ObjectType[]
  linkTypes: LinkType[]
  interfaces: InterfaceDef[]
  actionTypes: ActionType[]
  functions: FunctionDef[]
  objects: OntologyObject[]
  selectedObjectTypeId: string | null
  setObjectTypes: (data: ObjectType[]) => void
  setLinkTypes: (data: LinkType[]) => void
  setInterfaces: (data: InterfaceDef[]) => void
  setActionTypes: (data: ActionType[]) => void
  setFunctions: (data: FunctionDef[]) => void
  setObjects: (data: OntologyObject[]) => void
  setSelectedObjectTypeId: (id: string | null) => void
}

export const useOntologyStore = create<OntologyState>((set) => ({
  objectTypes: [],
  linkTypes: [],
  interfaces: [],
  actionTypes: [],
  functions: [],
  objects: [],
  selectedObjectTypeId: null,
  setObjectTypes: (data) => set({ objectTypes: data }),
  setLinkTypes: (data) => set({ linkTypes: data }),
  setInterfaces: (data) => set({ interfaces: data }),
  setActionTypes: (data) => set({ actionTypes: data }),
  setFunctions: (data) => set({ functions: data }),
  setObjects: (data) => set({ objects: data }),
  setSelectedObjectTypeId: (id) => set({ selectedObjectTypeId: id }),
}))
