import { useCallback, useRef, type DragEvent } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  BackgroundVariant,
  type OnNodesChange,
  type OnEdgesChange,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './canvas-theme.css'

import ClientNode from './nodes/ClientNode'
import ServerNode from './nodes/ServerNode'
import StrategyNode from './nodes/StrategyNode'
import RouteNode from './nodes/RouteNode'
import DirectNode from './nodes/DirectNode'
import DetourEdge from './edges/DetourEdge'

const nodeTypes: NodeTypes = {
  clientNode: ClientNode,
  serverNode: ServerNode,
  strategyNode: StrategyNode,
  routeNode: RouteNode,
  directNode: DirectNode,
}

const edgeTypes: EdgeTypes = {
  detour: DetourEdge,
}

const DEFAULT_CLIENT_NODE: Node = {
  id: 'client-1',
  type: 'clientNode',
  position: { x: 50, y: 200 },
  data: { label: 'Client' },
  deletable: false,
}

interface Props {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
  onNodeSelect: (node: Node | null) => void
}

let nodeId = 100

function getNextId() {
  return `node-${nodeId++}`
}

export default function Canvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  setNodes,
  setEdges,
  onNodeSelect,
}: Props) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge({ ...params, type: 'detour', animated: true }, eds)
      )
    },
    [setEdges]
  )

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()

      const rawType = event.dataTransfer.getData('application/reactflow')
      if (!rawType) return

      const bounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (!bounds) return

      const position = {
        x: event.clientX - bounds.left - 80,
        y: event.clientY - bounds.top - 30,
      }

      let type = rawType
      let data: Record<string, unknown> = {}

      if (rawType.startsWith('strategyNode:')) {
        const strategyType = rawType.split(':')[1]
        type = 'strategyNode'
        data = {
          label: strategyType === 'urltest' ? 'URL Test' : strategyType === 'fallback' ? 'Fallback' : 'Selector',
          strategyType,
          testUrl: 'https://www.gstatic.com/generate_204',
          interval: '5m',
          tolerance: 50,
        }
      } else if (rawType === 'serverNode') {
        data = { label: 'Server', protocol: 'vless', serverId: '', status: '' }
      } else if (rawType === 'directNode') {
        data = { label: 'Direct' }
      } else if (rawType === 'routeNode') {
        const ruleId = `rule-${Date.now()}`
        data = {
          label: 'Route',
          rules: [{ id: ruleId, type: 'geoip:ru', value: 'ru', handleId: ruleId }],
        }
      }

      const newNode: Node = {
        id: getNextId(),
        type,
        position,
        data,
      }

      setNodes((nds) => [...nds, newNode])
    },
    [setNodes]
  )

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes }: { nodes: Node[] }) => {
      onNodeSelect(selectedNodes.length === 1 ? selectedNodes[0] : null)
    },
    [onNodeSelect]
  )

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onSelectionChange={onSelectionChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        defaultEdgeOptions={{ type: 'detour', animated: true }}
        fitView
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
        className="chain-editor-canvas"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="hsla(228, 8%, 30%, 0.4)"
        />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={() => 'hsl(187, 85%, 53%)'}
          maskColor="hsla(228, 16%, 4%, 0.85)"
        />
      </ReactFlow>
    </div>
  )
}

export { DEFAULT_CLIENT_NODE }
export { useNodesState, useEdgesState }
