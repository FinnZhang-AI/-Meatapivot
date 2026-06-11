import { useState, useRef, useEffect } from 'react'
import { useAgentList, useAgentRun } from '../../hooks/useAIP'
import type { AgentStep, AgentRunResponse } from '../../types/aip'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  steps?: AgentStep[]
}

export default function AgentChat() {
  const { data: agents, isLoading: agentsLoading } = useAgentList()
  const runAgent = useAgentRun()
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (agents && agents.length > 0 && !selectedAgent) {
      setSelectedAgent(agents[0].id)
    }
  }, [agents, selectedAgent])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || !selectedAgent || isRunning) return
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsRunning(true)

    try {
      const result: AgentRunResponse = await runAgent.mutateAsync({
        agentId: selectedAgent,
        input: userMsg.content,
      })
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.output,
        timestamp: new Date().toISOString(),
        steps: result.steps,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: 'system',
        content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsRunning(false)
    }
  }

  const toggleSteps = (msgId: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev)
      if (next.has(msgId)) next.delete(msgId)
      else next.add(msgId)
      return next
    })
  }

  const getStepIcon = (type: string) => {
    switch (type) {
      case 'llm': return '🧠'
      case 'answer': return '✅'
      case 'llm_error': return '❌'
      default: return '⚙️'
    }
  }

  return (
    <div className="flex h-[calc(100vh-120px)]">
      {/* Agent selector sidebar */}
      <div className="w-64 border-r border-gray-200 bg-gray-50 p-4 flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Agent</h3>
        {agentsLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : (
          agents?.map(agent => (
            <button
              key={agent.id}
              onClick={() => {
                setSelectedAgent(agent.id)
                setMessages([])
              }}
              className={`text-left p-3 rounded-lg text-sm transition ${
                selectedAgent === agent.id
                  ? 'bg-blue-100 border border-blue-300'
                  : 'bg-white border border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="font-medium">{agent.name}</div>
              <div className="text-xs text-gray-500 mt-1">{agent.workflowMode} · {agent.model}</div>
            </button>
          ))
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-20">
              <div className="text-4xl mb-4">🤖</div>
              <p>Select an agent and start a conversation</p>
            </div>
          )}
          {messages.map(msg => (
            <div key={msg.id}>
              <div className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role !== 'user' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm shrink-0">
                    {msg.role === 'system' ? '⚠️' : '🤖'}
                  </div>
                )}
                <div className={`max-w-[75%] rounded-xl p-4 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : msg.role === 'system'
                    ? 'bg-red-50 text-red-700 border border-red-200'
                    : 'bg-white border border-gray-200 text-gray-800'
                }`}>
                  <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                  {msg.steps && msg.steps.length > 0 && (
                    <button
                      onClick={() => toggleSteps(msg.id)}
                      className={`mt-2 text-xs font-medium flex items-center gap-1 ${
                        msg.role === 'user' ? 'text-blue-200' : 'text-blue-600'
                      }`}
                    >
                      {expandedSteps.has(msg.id) ? '▲' : '▼'} 
                      {msg.steps.length} step{msg.steps.length > 1 ? 's' : ''}
                    </button>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm shrink-0">
                    U
                  </div>
                )}
              </div>
              {/* Steps timeline */}
              {msg.steps && expandedSteps.has(msg.id) && (
                <div className="ml-12 mt-2 border-l-2 border-blue-200 pl-4 space-y-2">
                  {msg.steps.map((step, i) => (
                    <div key={i} className="text-xs">
                      <div className="flex items-center gap-2">
                        <span>{getStepIcon(step.type)}</span>
                        <span className="font-medium text-gray-600">{step.type}</span>
                        {step.durationMs && (
                          <span className="text-gray-400">{step.durationMs}ms</span>
                        )}
                      </div>
                      {step.thought && (
                        <div className="text-gray-500 mt-1 italic">"{step.thought.slice(0, 200)}"</div>
                      )}
                      {step.toolCalls?.map((tc, j) => (
                        <div key={j} className="mt-1 bg-gray-50 p-2 rounded">
                          <div className="text-blue-600 font-mono">🔧 {tc.tool}</div>
                          <div className="text-gray-400 mt-0.5">{JSON.stringify(tc.args)}</div>
                          <div className="text-gray-700 mt-1">{tc.result.slice(0, 300)}</div>
                        </div>
                      ))}
                      {step.content && step.type === 'answer' && (
                        <div className="text-green-700 mt-1">{step.content.slice(0, 200)}</div>
                      )}
                      {step.error && (
                        <div className="text-red-500 mt-1">{step.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder={selectedAgent ? `Message ${agents?.find(a => a.id === selectedAgent)?.name}...` : 'Select an agent first'}
              className="flex-1 resize-none rounded-lg border border-gray-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              disabled={isRunning || !selectedAgent}
            />
            <button
              onClick={handleSend}
              disabled={isRunning || !input.trim() || !selectedAgent}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {isRunning ? '...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
