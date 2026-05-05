import { useEffect, useRef, useState, useCallback } from 'react'
import type { GraphNode, GraphEdge } from '../../types/ontology'

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick?: (node: GraphNode) => void
  height?: number
}

interface SimNode extends GraphNode {
  x: number
  y: number
  vx: number
  vy: number
}

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
]

function getColor(type: string) {
  let hash = 0
  for (let i = 0; i < type.length; i++) {
    hash = type.charCodeAt(i) + ((hash << 5) - hash)
  }
  return COLORS[Math.abs(hash) % COLORS.length]
}

export default function OntologyGraph({ nodes, edges, onNodeClick, height = 400 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [simNodes, setSimNodes] = useState<SimNode[]>([])
  const [simEdges, setSimEdges] = useState<GraphEdge[]>([])
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const animationRef = useRef<number>(0)
  const draggingRef = useRef<string | null>(null)
  const mouseRef = useRef({ x: 0, y: 0 })

  // Initialize simulation
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const width = canvas.clientWidth
    const centerX = width / 2
    const centerY = height / 2

    const initialized: SimNode[] = nodes.map((n, i) => ({
      ...n,
      x: n.x || centerX + Math.cos((i / nodes.length) * Math.PI * 2) * 100,
      y: n.y || centerY + Math.sin((i / nodes.length) * Math.PI * 2) * 100,
      vx: 0,
      vy: 0,
    }))

    setSimNodes(initialized)
    setSimEdges(edges)
  }, [nodes, edges, height])

  // Force simulation loop
  useEffect(() => {
    if (simNodes.length === 0) return

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.clientWidth
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    const repulsion = 2000
    const springLength = 120
    const springStrength = 0.05
    const centerGravity = 0.01
    const damping = 0.9

    let currentNodes = [...simNodes]

    const step = () => {
      // Repulsion
      for (let i = 0; i < currentNodes.length; i++) {
        for (let j = i + 1; j < currentNodes.length; j++) {
          const a = currentNodes[i]
          const b = currentNodes[j]
          const dx = b.x - a.x
          const dy = b.y - a.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = repulsion / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          if (!draggingRef.current || draggingRef.current !== a.id) {
            a.vx -= fx
            a.vy -= fy
          }
          if (!draggingRef.current || draggingRef.current !== b.id) {
            b.vx += fx
            b.vy += fy
          }
        }
      }

      // Spring attraction along edges
      for (const edge of simEdges) {
        const a = currentNodes.find((n) => n.id === edge.source)
        const b = currentNodes.find((n) => n.id === edge.target)
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - springLength) * springStrength
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        if (!draggingRef.current || draggingRef.current !== a.id) {
          a.vx += fx
          a.vy += fy
        }
        if (!draggingRef.current || draggingRef.current !== b.id) {
          b.vx -= fx
          b.vy -= fy
        }
      }

      // Center gravity
      const cx = width / 2
      const cy = height / 2
      for (const n of currentNodes) {
        if (draggingRef.current === n.id) continue
        n.vx += (cx - n.x) * centerGravity
        n.vy += (cy - n.y) * centerGravity
      }

      // Update positions
      for (const n of currentNodes) {
        if (draggingRef.current === n.id) {
          n.vx = 0
          n.vy = 0
          continue
        }
        n.vx *= damping
        n.vy *= damping
        n.x += n.vx
        n.y += n.vy
        // Boundary
        n.x = Math.max(20, Math.min(width - 20, n.x))
        n.y = Math.max(20, Math.min(height - 20, n.y))
      }

      // Render
      ctx.clearRect(0, 0, width, height)

      // Draw edges
      for (const edge of simEdges) {
        const a = currentNodes.find((n) => n.id === edge.source)
        const b = currentNodes.find((n) => n.id === edge.target)
        if (!a || !b) continue
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = hoveredNode && (edge.source === hoveredNode || edge.target === hoveredNode)
          ? '#94a3b8'
          : '#e2e8f0'
        ctx.lineWidth = hoveredNode && (edge.source === hoveredNode || edge.target === hoveredNode) ? 2 : 1
        ctx.stroke()
      }

      // Draw nodes
      for (const n of currentNodes) {
        const isHovered = hoveredNode === n.id
        const color = getColor(n.objectType)
        const radius = isHovered ? 24 : 20

        ctx.beginPath()
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
        if (isHovered) {
          ctx.strokeStyle = '#1e293b'
          ctx.lineWidth = 3
          ctx.stroke()
        }

        // Label
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 11px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const label = n.label.length > 8 ? n.label.slice(0, 8) + '...' : n.label
        ctx.fillText(label, n.x, n.y)

        // Type label below
        ctx.fillStyle = '#64748b'
        ctx.font = '9px sans-serif'
        ctx.fillText(n.objectType, n.x, n.y + radius + 12)
      }

      animationRef.current = requestAnimationFrame(step)
    }

    animationRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(animationRef.current)
  }, [simNodes, simEdges, hoveredNode, height])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    mouseRef.current = { x, y }

    if (draggingRef.current) {
      setSimNodes((prev) =>
        prev.map((n) => (n.id === draggingRef.current ? { ...n, x, y, vx: 0, vy: 0 } : n))
      )
      return
    }

    // Find hovered node
    for (const n of simNodes) {
      const dx = x - n.x
      const dy = y - n.y
      if (Math.sqrt(dx * dx + dy * dy) < 24) {
        setHoveredNode(n.id)
        return
      }
    }
    setHoveredNode(null)
  }, [simNodes])

  const handleMouseDown = useCallback(() => {
    if (hoveredNode) {
      draggingRef.current = hoveredNode
    }
  }, [hoveredNode])

  const handleMouseUp = useCallback(() => {
    draggingRef.current = null
  }, [])

  const handleClick = useCallback(() => {
    if (hoveredNode) {
      const node = simNodes.find((n) => n.id === hoveredNode)
      if (node && onNodeClick) {
        onNodeClick(node)
      }
    }
  }, [hoveredNode, simNodes, onNodeClick])

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded-lg border border-slate-200 dark:border-slate-700 cursor-grab active:cursor-grabbing"
      style={{ height }}
      onMouseMove={handleMouseMove}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onClick={handleClick}
    />
  )
}
