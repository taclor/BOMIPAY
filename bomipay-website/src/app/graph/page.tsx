'use client'

import { useState, useCallback } from 'react'
import Shell from '@/components/layout/Shell'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Search, X } from 'lucide-react'
import type { PaymentGraph, GraphNode } from '@/types/api'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'

const NODE_COLORS: Record<string, string> = {
  transaction: '#3b82f6',
  settlement: '#10b981',
  dispute: '#ef4444',
  incident: '#f97316',
  bank_entry: '#14b8a6',
}

const MOCK_GRAPH: PaymentGraph = {
  transaction_id: 'TXN-00891',
  nodes: [
    { id: 'txn-1', type: 'transaction', label: 'TXN-00891', data: { amount: 45000000, provider: 'paystack', status: 'success' } },
    { id: 'settle-1', type: 'settlement', label: 'Settlement #S-4421', data: { amount: 44775000, date: new Date().toISOString() } },
    { id: 'bank-1', type: 'bank_entry', label: 'Bank Entry B-1291', data: { amount: 44775000, description: 'PAYSTACK SETTLEMENT' } },
    { id: 'webhook-1', type: 'transaction', label: 'Webhook: payment.success', data: { provider: 'paystack', event: 'payment.success' } },
  ],
  edges: [
    { id: 'e1', source: 'txn-1', target: 'settle-1', label: 'settled_via', relationship_type: 'settled_via' },
    { id: 'e2', source: 'settle-1', target: 'bank-1', label: 'matched_to', relationship_type: 'matched_to' },
    { id: 'e3', source: 'txn-1', target: 'webhook-1', label: 'triggered', relationship_type: 'triggered' },
  ],
}

function graphToFlow(graph: PaymentGraph): { nodes: Node[]; edges: Edge[] } {
  const cols = 3
  const nodeWidth = 180
  const nodeHeight = 60
  const colSpacing = 220
  const rowSpacing = 100

  const nodes: Node[] = graph.nodes.map((n, i) => ({
    id: n.id,
    type: 'default',
    position: n.position ?? { x: (i % cols) * colSpacing + 50, y: Math.floor(i / cols) * rowSpacing + 50 },
    data: { label: n.label, nodeType: n.type, nodeData: n.data },
    style: {
      background: `${NODE_COLORS[n.type] ?? '#6b7280'}22`,
      border: `1.5px solid ${NODE_COLORS[n.type] ?? '#6b7280'}`,
      color: '#111827',
      fontSize: 11,
      fontFamily: 'monospace',
      borderRadius: 6,
      width: nodeWidth,
      minHeight: nodeHeight,
      padding: '8px 12px',
    },
  }))

  const edges: Edge[] = graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    style: { stroke: '#D1D5DB', strokeWidth: 1.5 },
    labelStyle: { fill: '#6B7280', fontSize: 10, fontFamily: 'monospace' },
    labelBgStyle: { fill: '#FFFFFF', fillOpacity: 0.9 },
  }))

  return { nodes, edges }
}

function NodeDetail({ node, graphNode, onClose }: { node: Node; graphNode: GraphNode | undefined; onClose: () => void }) {
  if (!graphNode) return null
  return (
    <div className="absolute right-4 top-4 w-64 bg-white border border-gray-200 rounded-lg p-4 z-10 shadow-md">
      <div className="flex items-center justify-between mb-3">
        <div>
          <span
            className="text-[10px] uppercase tracking-wider font-mono px-1.5 py-0.5 rounded"
            style={{ background: `${NODE_COLORS[graphNode.type] ?? '#6b7280'}22`, color: NODE_COLORS[graphNode.type] ?? '#6b7280' }}
          >
            {graphNode.type}
          </span>
          <p className="text-xs font-semibold text-gray-900 mt-1">{graphNode.label}</p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="space-y-1.5">
        {Object.entries(graphNode.data).map(([k, v]) => (
          <div key={k} className="flex justify-between text-[11px]">
            <span className="text-gray-500 capitalize">{k.replace(/_/g, ' ')}</span>
            <span className="text-gray-700 font-mono text-right max-w-[120px] truncate">{String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function GraphPage() {
  const [txnId, setTxnId] = useState('')
  const [searchId, setSearchId] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const { data: graph, refetch } = useQuery({
    queryKey: ['graph', searchId],
    queryFn: async () => {
      const { data } = await api.get<PaymentGraph>(`/payment-graph/transactions/${searchId}`)
      return data
    },
    placeholderData: MOCK_GRAPH,
    enabled: true,
  })

  const { nodes: initialNodes, edges: initialEdges } = graphToFlow(graph ?? MOCK_GRAPH)
  const [nodes, , onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState(initialEdges)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchId(txnId)
  }

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id)
  }, [])

  const selectedGraphNode = graph?.nodes.find((n) => n.id === selectedNodeId)
  const selectedFlowNode = nodes.find((n) => n.id === selectedNodeId)

  return (
    <Shell title="Payment Graph Explorer" onRefresh={() => refetch()}>
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" />
          <input
            value={txnId}
            onChange={(e) => setTxnId(e.target.value)}
            placeholder="Search transaction ID (e.g. TXN-00891)…"
            className="w-full bg-white border border-gray-200 rounded-lg pl-9 pr-4 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button type="submit" className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm transition-colors">
          Explore
        </button>
      </form>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-4">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
            <span className="text-[10px] text-gray-500 capitalize">{type.replace('_', ' ')}</span>
          </div>
        ))}
      </div>

      {/* Graph */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden relative" style={{ height: 'calc(100vh - 18rem)' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
        >
          <Background variant={BackgroundVariant.Dots} color="#1f2937" gap={20} size={1} />
          <Controls />
          <MiniMap
            style={{ background: '#F8FAFC', border: '1px solid #E5E7EB' }}
            nodeColor={(n) => NODE_COLORS[(n.data as { nodeType?: string })?.nodeType ?? ''] ?? '#6b7280'}
          />
        </ReactFlow>

        {selectedNodeId && selectedFlowNode && selectedGraphNode && (
          <NodeDetail
            node={selectedFlowNode}
            graphNode={selectedGraphNode}
            onClose={() => setSelectedNodeId(null)}
          />
        )}
      </div>
    </Shell>
  )
}
