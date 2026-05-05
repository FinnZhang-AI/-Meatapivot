import { useState } from 'react'
import type { ChatMessage } from '../../types/aip'

interface Props {
  message: ChatMessage
}

function parseMarkdown(text: string): JSX.Element {
  const lines = text.split('\n')
  const elements: JSX.Element[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      elements.push(
        <CodeBlock key={i} code={codeLines.join('\n')} lang={lang} />
      )
      continue
    }

    // Bold
    const bolded = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Inline code
    const coded = bolded.replace(/`(.+?)`/g, '<code>$1</code>')

    elements.push(
      <p
        key={i}
        className="mb-1 last:mb-0"
        dangerouslySetInnerHTML={{ __html: coded }}
      />
    )
    i++
  }

  return <>{elements}</>
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-2 rounded-lg overflow-hidden bg-slate-900">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800">
        <span className="text-xs text-slate-400">{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="text-xs text-slate-400 hover:text-white transition-colors"
        >
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <pre className="px-4 py-3 overflow-x-auto text-sm text-slate-200">
        <code>{code}</code>
      </pre>
    </div>
  )
}

export default function ChatMessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-5 py-3 ${
          isUser
            ? 'bg-primary text-white rounded-br-md'
            : 'bg-slate-100 dark:bg-slate-700 text-slate-900 dark:text-white rounded-bl-md'
        }`}
      >
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {parseMarkdown(message.content)}
        </div>
        <div className={`text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-slate-400'}`}>
          {message.model && <span className="mr-2">{message.model}</span>}
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
