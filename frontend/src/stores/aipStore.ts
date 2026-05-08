import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ChatMessage } from '../types/aip'

const STORAGE_KEY = 'meatapivot_chat_session'

function generateSessionId(): string {
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

interface AIPState {
  sessionId: string
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
  startNewChat: () => void
}

export const useAIPStore = create<AIPState>()(
  persist(
    (set) => ({
      sessionId: generateSessionId(),
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
      startNewChat: () =>
        set({ sessionId: generateSessionId(), messages: [] }),
    }),
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        sessionId: state.sessionId,
        messages: state.messages,
        currentModel: state.currentModel,
        temperature: state.temperature,
        streamMode: state.streamMode,
      }),
    }
  )
)
