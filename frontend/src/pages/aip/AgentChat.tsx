import { useState, useRef, useEffect } from 'react'
import {
  useAgentList,
  useAgentRun,
  useAgentStatus,
  useAgentInterrupt,
  useAgentResume,
  useAgentStream,
} from '../../hooks/useAIP'
import type { AgentStep, AgentRunResponse } from '../../types/aip'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  steps?: AgentStep[]
  traceId?: string
  status?: AgentRunResponse['status']
  requiresInput?: boolean
  prompt?: string
}

export default function AgentChat() {
  const { data: agents, isLoading: agentsLoading } = useAgentList()
  const runAgent = useAgentRun()
  const statusAgent = useAgentStatus()
  const interruptAgent = useAgentInterrupt()
  const resumeAgent = useAgentResume()
  const { streamRun } = useAgentStream()
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())
  const [streamEnabled, setStreamEnabled] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (agents && agents.length > 0 && !selectedAgent) {
      setSelectedAgent(agents[0].id)
    }
  }, [agents, selectedAgent])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const appendMessage = (msg: Message) => {
    setMessages(prev => [...prev, msg])
  }

  const updateLastAssistant = (update: Partial<Message>) => {
    setMessages(prev => {
      const lastIndex = prev.length - 1
      if (lastIndex < 0) return prev
      const last = prev[lastIndex]
      if (last.role !== 'assistant') return prev
      const next = [...prev]
      next[lastIndex] = { ...last, ...update }
      return next
    })
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedAgent || isRunning) return
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }
    appendMessage(userMsg)
    setInput('')
    setIsRunning(true)

    if (streamEnabled) {
      await runWithStream(userMsg.content)
    } else {
      await runWithPolling(userMsg.content)
    }
  }

  const runWithPolling = async (userInput: string) => {
    try {
      const result: AgentRunResponse = await runAgent.mutateAsync({
        agentId: selectedAgent,
        input: userInput,
      })
      appendMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.output,
        timestamp: new Date().toISOString(),
        steps: result.steps,
        traceId: result.traceId,
        status: result.status as AgentRunResponse['status'],
        requiresInput: result.requiresInput,
        prompt: result.prompt,
      })
    } catch (err) {
      appendError(err)
    } finally {
      setIsRunning(false)
    }
  }

  const runWithStream = async (userInput: string) => {
    const assistantMsgId = crypto.randomUUID()
    appendMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      steps: [],
      status: 'running',
    })

    try {
      await streamRun(
        { agentId: selectedAgent, input: userInput },
        (event) => {
          if (event.event === 'status' && event.data?.status === 'running') {
            updateLastAssistant({ status: 'running', traceId: event.trace_id })
            return
          }
          if (event.event === 'step' && event.data) {
            const step = event.data as AgentStep
            setMessages(prev => {
              const lastIndex = prev.length - 1
              if (lastIndex < 0) return prev
              const last = prev[lastIndex]
              if (last.role !== 'assistant') return prev
              const next = [...prev]
              const existing = next[lastIndex].steps || []
              // Replace if same type/thought to avoid duplicates, else append
              const idx = existing.findIndex(s =>
                s.type === step.type && s.thought === step.thought && s.content === step.content
              )
              const newSteps = idx >= 0
                ? existing.map((s, i) => (i === idx ? step : s))
                : [...existing, step]
              next[lastIndex] = {
                ...last,
                steps: newSteps,
                content: step.type === 'answer' ? step.content || '' : last.content,
              }
              return next
            })
          }
          if (event.event === 'human_input_required') {
            updateLastAssistant({
              status: 'awaiting_input',
              requiresInput: true,
              prompt: event.data?.prompt,
              traceId: event.trace_id,
            })
            setIsRunning(false)
          }
          if (event.event === 'completed') {
            updateLastAssistant({
              status: 'completed',
              content: event.data?.output || '',
              traceId: event.trace_id,
            })
            setIsRunning(false)
          }
          if (event.event === 'failed' || event.event === 'interrupted') {
            updateLastAssistant({
              status: event.event === 'failed' ? 'failed' : 'interrupted',
              content: event.data?.output || event.data?.error || '',
              traceId: event.trace_id,
            })
            setIsRunning(false)
          }
        },
      )
      setIsRunning(false)
    } catch (err) {
      updateLastAssistant({ status: 'failed', content: String(err) })
      setIsRunning(false)
    }
  }

  const appendError = (err: unknown) => {
    appendMessage({
      id: crypto.randomUUID(),
      role: 'system',
      content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
      timestamp: new Date().toISOString(),
    })
  }

  const handleInterrupt = async () => {
    const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant' && m.traceId)
    if (!lastAssistant?.traceId || !selectedAgent) return
    try {
      await interruptAgent.mutateAsync({ agentId: selectedAgent, traceId: lastAssistant.traceId })
      updateLastAssistant({ status: 'interrupted', content: 'Agent interrupted by user.' })
      setIsRunning(false)
    } catch (err) {
      appendError(err)
    }
  }

  const handleResume = async (msg: Message) => {
    if (!msg.traceId || !selectedAgent || isRunning) return
    setIsRunning(true)
    try {
      const result: AgentRunResponse = await resumeAgent.mutateAsync({
        agentId: selectedAgent,
        traceId: msg.traceId,
        input: input.trim() || 'yes',
      })
      setInput('')
      appendMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.output,
        timestamp: new Date().toISOString(),
        steps: result.steps,
        traceId: result.traceId,
        status: result.status as AgentRunResponse['status'],
        requiresInput: result.requiresInput,
        prompt: result.prompt,
      })
    } catch (err) {
      appendError(err)
    } finally {
      setIsRunning(false)
    }
  }

  const handleRetry = async () => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUser || !selectedAgent || isRunning) return
    setIsRunning(true)
    if (streamEnabled) {
      await runWithStream(lastUser.content)
    } else {
      await runWithPolling(lastUser.content)
    }
  }

  const handleRefreshStatus = async () => {
    const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant' && m.traceId)
    if (!lastAssistant?.traceId || !selectedAgent) return
    try {
      const result = await statusAgent.mutateAsync({ agentId: selectedAgent, traceId: lastAssistant.traceId })
      updateLastAssistant({
        status: result.status as AgentRunResponse['status'],
        content: result.output,
        steps: result.steps,
        requiresInput: result.requiresInput,
        prompt: result.prompt,
      })
    } catch (err) {
      appendError(err)
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

  const waitingMessage = [...messages].reverse().find(m => m.role === 'assistant' && m.requiresInput)

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
              <div className="text-xs text-gray-500 mt-1">{agent.workflow_mode} · {agent.model}</div>
            </button>
          ))
        )}

        <div className="mt-auto pt-4 border-t border-gray-200">
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={streamEnabled}
              onChange={e => setStreamEnabled(e.target.checked)}
              className="rounded border-gray-300"
            />
            Stream steps (SSE)
          </label>
        </div>
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
                  <div className="whitespace-pre-wrap text-sm">{msg.content || (msg.status === 'running' ? 'Thinking...' : '')}</div>
                  {msg.status && msg.role === 'assistant' && (
                    <div className="mt-2 flex items-center gap-2 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        msg.status === 'completed' ? 'bg-green-100 text-green-700' :
                        msg.status === 'running' ? 'bg-blue-100 text-blue-700' :
                        msg.status === 'awaiting_input' ? 'bg-yellow-100 text-yellow-700' :
                        msg.status === 'interrupted' ? 'bg-orange-100 text-orange-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {msg.status}
                      </span>
                      {msg.traceId && (
                        <span className="text-xs text-gray-400 font-mono">{msg.traceId.slice(0, 8)}</span>
                      )}
                    </div>
                  )}
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
                  {msg.role === 'assistant' && msg.requiresInput && (
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => handleResume(msg)}
                        className="px-3 py-1.5 bg-yellow-500 text-white rounded text-xs font-medium hover:bg-yellow-600"
                      >
                        Resume
                      </button>
                    </div>
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

        {/* Toolbar */}
        <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 flex gap-2">
          {isRunning && (
            <button
              onClick={handleInterrupt}
              className="px-3 py-1.5 bg-orange-100 text-orange-700 rounded text-xs font-medium hover:bg-orange-200"
            >
              ⏹ Interrupt
            </button>
          )}
          {!isRunning && messages.some(m => m.role === 'assistant' && m.traceId) && (
            <>
              <button
                onClick={handleRetry}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200"
              >
                🔄 Retry last
              </button>
              <button
                onClick={handleRefreshStatus}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200"
              >
                Refresh status
              </button>
            </>
          )}
          {waitingMessage && !isRunning && (
            <span className="text-xs text-yellow-700 flex items-center">
              ⏸ Waiting for input on {waitingMessage.traceId?.slice(0, 8)}
            </span>
          )}
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
              placeholder={
                waitingMessage
                  ? 'Provide input to resume agent...'
                  : selectedAgent
                  ? `Message ${agents?.find(a => a.id === selectedAgent)?.name}...`
                  : 'Select an agent first'
              }
              className="flex-1 resize-none rounded-lg border border-gray-300 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              disabled={isRunning || !selectedAgent}
            />
            <button
              onClick={handleSend}
              disabled={isRunning || !input.trim() || !selectedAgent}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {isRunning ? '...' : waitingMessage ? 'Resume' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
