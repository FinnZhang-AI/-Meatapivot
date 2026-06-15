import { useEffect, useState } from 'react'
import type { InterfaceValidationReport } from '../hooks/useInterfaceValidationWS'

/**
 * Listens for `meatapivot:interface-validation` window events and surfaces a
 * short-lived toast. Intentionally tiny — we don't pull in a toast library
 * just for this single notification.
 */
const ValidationToaster = () => {
  const [toast, setToast] = useState<InterfaceValidationReport | null>(null)

  useEffect(() => {
    const onEvent = (event: Event) => {
      const ce = event as CustomEvent<InterfaceValidationReport>
      if (!ce.detail) return
      setToast(ce.detail)
      const timer = window.setTimeout(() => setToast(null), 6000)
      return () => window.clearTimeout(timer)
    }
    window.addEventListener('meatapivot:interface-validation', onEvent as EventListener)
    return () => {
      window.removeEventListener('meatapivot:interface-validation', onEvent as EventListener)
    }
  }, [])

  if (!toast) return null

  const isFailed = toast.status === 'failed'
  const failedCount = toast.interfaces_failed ?? 0
  const total = toast.interfaces_total ?? 0

  let headline: string
  let tone: 'green' | 'red' | 'blue'
  if (isFailed) {
    headline = `Interface 校验失败：${toast.error ?? 'unknown error'}`
    tone = 'red'
  } else if (failedCount > 0) {
    headline = `Interface 校验完成：${failedCount} / ${total} 个存在不一致`
    tone = 'red'
  } else if (total === 0) {
    headline = 'Interface 校验完成：当前租户没有 Interface'
    tone = 'blue'
  } else {
    headline = `Interface 校验完成：${total} 个全部通过`
    tone = 'green'
  }

  const toneClass: Record<typeof tone, string> = {
    green: 'border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-100',
    red: 'border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-900/30 dark:text-rose-100',
    blue: 'border-sky-500 bg-sky-50 text-sky-900 dark:bg-sky-900/30 dark:text-sky-100',
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm">
      <div
        role="status"
        className={`rounded-lg border-l-4 shadow-lg p-4 ${toneClass[tone]}`}
      >
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-medium">{headline}</p>
          <button
            type="button"
            className="text-xs opacity-70 hover:opacity-100"
            onClick={() => setToast(null)}
            aria-label="关闭通知"
          >
            ✕
          </button>
        </div>
        {toast.completed_at && (
          <p className="mt-1 text-xs opacity-70">
            {new Date(toast.completed_at).toLocaleString('zh-CN')}
          </p>
        )}
      </div>
    </div>
  )
}

export default ValidationToaster
