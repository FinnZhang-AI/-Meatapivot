import { useEffect, useRef, useState } from 'react'

export interface InterfaceValidationReport {
  status: 'completed' | 'failed'
  tenant_id: string
  interfaces_total?: number
  interfaces_failed?: number
  results?: Array<{
    interface_id: string
    interface_name: string
    implementations_total: number
    passed: number
    failed: number
  }>
  error?: string
  completed_at?: string
}

export interface UseInterfaceValidationWSResult {
  report: InterfaceValidationReport | null
  connected: boolean
  error: string | null
}

/**
 * Subscribe to the S3-1 interface validation WebSocket and expose the latest
 * report. Dispatches a `meatapivot:interface-validation` window CustomEvent
 * on every push so any UI surface (toast, banner, badge) can react without
 * pulling in a notification library.
 */
export function useInterfaceValidationWS(
  tenantId: string | null | undefined,
  options: { onReport?: (report: InterfaceValidationReport) => void } = {}
): UseInterfaceValidationWSResult {
  const [report, setReport] = useState<InterfaceValidationReport | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number | null>(null)
  const onReportRef = useRef(options.onReport)
  onReportRef.current = options.onReport

  useEffect(() => {
    if (!tenantId) return

    let cancelled = false

    const connect = () => {
      if (cancelled) return
      const base = import.meta.env.VITE_WS_BASE_URL
        || (window.location.protocol === 'https:'
          ? `wss://${window.location.host}`
          : `ws://${window.location.host}`)
      const url = `${base}/ws/interfaces/${encodeURIComponent(tenantId)}`

      let ws: WebSocket
      try {
        ws = new WebSocket(url)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
        scheduleReconnect()
        return
      }
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setError(null)
      }
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as InterfaceValidationReport
          setReport(payload)
          onReportRef.current?.(payload)
          // Surface to the rest of the app without coupling to a UI lib
          window.dispatchEvent(
            new CustomEvent('meatapivot:interface-validation', { detail: payload })
          )
        } catch (parseErr) {
          // Ignore malformed frames; the next push will replace this one
          console.warn('Failed to parse interface validation payload', parseErr)
        }
      }
      ws.onerror = () => {
        setError('WebSocket error')
      }
      ws.onclose = () => {
        setConnected(false)
        wsRef.current = null
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (cancelled) return
      if (reconnectRef.current !== null) return
      reconnectRef.current = window.setTimeout(() => {
        reconnectRef.current = null
        connect()
      }, 3000)
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectRef.current !== null) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [tenantId])

  return { report, connected, error }
}
