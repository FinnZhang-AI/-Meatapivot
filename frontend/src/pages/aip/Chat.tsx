import { useState, useRef, useEffect, useCallback } from 'react'
import { useAIPStore } from '../../stores/aipStore'
import { useStreamChat, useChat } from '../../hooks/useAIP'
import ChatMessageBubble from '../../components/aip/ChatMessageBubble'
import type { ChatMessage } from '../../types/aip'

const MODELS = [
  { id: 'gpt-4o', name: 'GPT-4o' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
  { id: 'claude-3-5-sonnet', name: 'Claude 3.5 Sonnet' },
  { id: 'llama-3.1-70b', name: 'Llama 3.1 70B' },
]

export default function Chat() {
  const { messages, addMessage, currentModel, setCurrentModel, temperature, setTemperature, streamMode, setStreamMode, startNewChat } = useAIPStore()
  const { streamChat, isStreaming, abort } = useStreamChat()
  const { mutateAsync: chatAsync } = useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || isStreaming) return
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }
    addMessage(userMessage)
    setInput('')

    if (streamMode) {
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        model: currentModel,
      }
      addMessage(assistantMessage)

      try {
        await streamChat(
          {
            messages: [...messages, userMessage],
            model: currentModel,
            temperature,
            stream: true,
          },
          (chunk) => {
            useAIPStore.setState((state) => {
              const msgs = [...state.messages]
              const last = msgs[msgs.length - 1]
              if (last && last.role === 'assistant') {
                last.content += chunk.delta || ''
              }
              return { messages: msgs }
            })
          }
        )
      } catch (e) {
        console.error('Stream error:', e)
      }
    } else {
      try {
        const response = await chatAsync({
          messages: [...messages, userMessage],
          model: currentModel,
          temperature,
          stream: false,
        })
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.message.content,
          timestamp: new Date().toISOString(),
          model: response.model,
        })
      } catch (e) {
        console.error('Chat error:', e)
        addMessage({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Error: ${e instanceof Error ? e.message : 'Unknown error'}`,
          timestamp: new Date().toISOString(),
        })
      }
    }
  }, [input, isStreaming, streamMode, messages, currentModel, temperature, addMessage, streamChat, chatAsync])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar */}
      <div className="w-64 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <button
            onClick={startNewChat}
            className="w-full px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
          >
            + 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <div className="text-xs text-slate-400 uppercase tracking-wider">今天</div>
          <div className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700 text-sm truncate cursor-pointer">
            当前对话
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-4">
            <select
              value={currentModel}
              onChange={(e) => setCurrentModel(e.target.value)}
              className="px-3 py-1.5 border rounded-lg text-sm dark:bg-slate-700 dark:border-slate-600 dark:text-white"
            >
              {MODELS.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              <label className="text-sm text-slate-600 dark:text-slate-400">温度</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-24"
              />
              <span className="text-sm text-slate-600 dark:text-slate-400 w-8">{temperature}</span>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
              <input
                type="checkbox"
                checked={streamMode}
                onChange={(e) => setStreamMode(e.target.checked)}
              />
              流式输出
            </label>
          </div>
          {isStreaming && (
            <button
              onClick={abort}
              className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 transition-colors"
            >
              停止
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-slate-400">
              <div className="text-center">
                <div className="text-4xl mb-4">🤖</div>
                <p className="text-lg font-medium"> Meatapivot AI 助手</p>
                <p className="text-sm mt-2">输入问题开始对话...</p>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <ChatMessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700">
          <div className="flex items-end gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息... (Shift+Enter 换行)"
              rows={1}
              className="flex-1 px-4 py-3 border rounded-xl resize-none dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50 max-h-32"
              style={{ minHeight: '48px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="px-6 py-3 bg-primary text-white rounded-xl font-medium hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isStreaming ? '...' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
