import { create } from 'zustand'
import { ChatMessage } from '../types/aip'

interface AIPState {
  messages: ChatMessage[]
  currentModel: string
  temperature: number
  streamMode: boolean
  isStreaming: boolean
  addMessage: (message: ChatMessage) => void
  setMessages: (messages: ChatMessage[]) => void
  setCurrentModel: (model: string) => void
  setTemperature: (temp: number) => void
  setStreamMode: (mode: boolean) => void
  setIsStreaming: (streaming: boolean) => void
  clearMessages: () => void
}

export const useAIPStore = create<AIPState>((set) => ({
  messages: [],
  currentModel: 'gpt-4o',
  temperature: 0.7,
  streamMode: true,
  isStreaming: false,
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setCurrentModel: (model) => set({ currentModel: model }),
  setTemperature: (temp) => set({ temperature: temp }),
  setStreamMode: (mode) => set({ streamMode: mode }),
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),
  clearMessages: () => set({ messages: [] }),
}))
