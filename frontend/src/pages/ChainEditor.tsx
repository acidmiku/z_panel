import { useState, useCallback, useEffect } from 'react'
import { useNodesState, useEdgesState } from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import { ReactFlowProvider } from '@xyflow/react'
import { Shield, Download, CheckCircle2, Save, FolderOpen, Trash2, Plus, UserCircle } from 'lucide-react'
import Canvas, { DEFAULT_CLIENT_NODE } from '@/components/chain-editor/Canvas'
import NodePalette from '@/components/chain-editor/NodePalette'
import ValidationPanel from '@/components/chain-editor/ValidationPanel'
import PropertiesPanel from '@/components/chain-editor/PropertiesPanel'
import ConfigPreview from '@/components/chain-editor/ConfigPreview'
import { useGraphValidation } from '@/components/chain-editor/hooks/useGraphValidation'
import { serializeGraph, deserializeGraph } from '@/components/chain-editor/utils/graphSerializer'
import { useServers } from '@/api/servers'
import { useUsers, type VPNUser } from '@/api/users'
import {
  useChainConfigs,
  useChainConfig,
  useCreateChainConfig,
  useUpdateChainConfig,
  useDeleteChainConfig,
  useExportChainConfig,
  useImportFromProfile,
} from '@/api/chain-configs'
import { useToast } from '@/components/Toaster'

function ChainEditorInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState([DEFAULT_CLIENT_NODE])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [generatedConfig, setGeneratedConfig] = useState<Record<string, unknown> | null>(null)
  const [activeConfigId, setActiveConfigId] = useState<string | null>(null)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [configName, setConfigName] = useState('')

  const { data: servers = [] } = useServers()
  const { data: users = [] } = useUsers()
  const { data: savedConfigs = [] } = useChainConfigs()
  const { data: loadedConfig } = useChainConfig(activeConfigId)
  const createConfig = useCreateChainConfig()
  const updateConfig = useUpdateChainConfig()
  const deleteConfig = useDeleteChainConfig()
  const exportConfig = useExportChainConfig()
  const importProfile = useImportFromProfile()
  const { toast } = useToast()

  const validation = useGraphValidation(nodes, edges)

  // Load config when activeConfigId changes
  useEffect(() => {
    if (loadedConfig?.graph_data) {
      const { nodes: loadedNodes, edges: loadedEdges } = deserializeGraph(loadedConfig.graph_data)
      setNodes(loadedNodes)
      setEdges(loadedEdges)
      setConfigName(loadedConfig.name)
    }
  }, [loadedConfig, setNodes, setEdges])

  const handleNodeSelect = useCallback((node: Node | null) => {
    setSelectedNode(node)
  }, [])

  const handleNodeDataUpdate = useCallback(
    (nodeId: string, data: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === nodeId ? { ...n, data } : n))
      )
    },
    [setNodes]
  )

  const handleValidate = useCallback(() => {
    if (validation.errors.length > 0) {
      toast({ title: 'Validation failed', description: `${validation.errors.length} error(s) found`, variant: 'destructive' })
    } else if (validation.warnings.length > 0) {
      toast({ title: 'Valid with warnings', description: `${validation.warnings.length} warning(s)` })
    } else {
      toast({ title: 'Graph is valid', description: 'Ready to export' })
    }
  }, [validation, toast])

  const handleExport = useCallback(async () => {
    if (validation.errors.length > 0) {
      toast({ title: 'Cannot export', description: 'Fix validation errors first', variant: 'destructive' })
      return
    }

    // If we have a saved config, export via API
    if (activeConfigId) {
      try {
        const config = await exportConfig.mutateAsync(activeConfigId)
        setGeneratedConfig(config)
        setShowConfig(true)
      } catch {
        toast({ title: 'Export failed', description: 'Could not generate config', variant: 'destructive' })
      }
      return
    }

    // Otherwise, save first then export
    const graphData = serializeGraph(nodes, edges)
    try {
      const saved = await createConfig.mutateAsync({
        name: configName || 'Untitled Chain',
        graph_data: graphData,
      })
      setActiveConfigId(saved.id)
      const config = await exportConfig.mutateAsync(saved.id)
      setGeneratedConfig(config)
      setShowConfig(true)
    } catch {
      toast({ title: 'Export failed', description: 'Could not save and generate config', variant: 'destructive' })
    }
  }, [validation, activeConfigId, nodes, edges, configName, exportConfig, createConfig, toast])

  const handleSave = useCallback(async () => {
    const graphData = serializeGraph(nodes, edges)

    if (activeConfigId) {
      try {
        await updateConfig.mutateAsync({ id: activeConfigId, graph_data: graphData, name: configName || 'Untitled Chain' })
        toast({ title: 'Saved', description: 'Chain config updated' })
      } catch {
        toast({ title: 'Save failed', variant: 'destructive' })
      }
    } else {
      setShowSaveDialog(true)
    }
  }, [activeConfigId, nodes, edges, configName, updateConfig, toast])

  const handleSaveNew = useCallback(async () => {
    if (!configName.trim()) return
    const graphData = serializeGraph(nodes, edges)
    try {
      const saved = await createConfig.mutateAsync({
        name: configName,
        graph_data: graphData,
      })
      setActiveConfigId(saved.id)
      setShowSaveDialog(false)
      toast({ title: 'Saved', description: `Config "${configName}" created` })
    } catch {
      toast({ title: 'Save failed', variant: 'destructive' })
    }
  }, [configName, nodes, edges, createConfig, toast])

  const handleLoad = useCallback((id: string) => {
    setActiveConfigId(id)
    setShowLoadDialog(false)
  }, [])

  const handleNew = useCallback(() => {
    setNodes([DEFAULT_CLIENT_NODE])
    setEdges([])
    setActiveConfigId(null)
    setConfigName('')
    setSelectedNode(null)
  }, [setNodes, setEdges])

  const handleImportProfile = useCallback(async (userId: string) => {
    try {
      const result = await importProfile.mutateAsync(userId)
      const { nodes: importedNodes, edges: importedEdges } = deserializeGraph(result.graph_data)
      setNodes(importedNodes)
      setEdges(importedEdges)
      setActiveConfigId(null)
      setConfigName(`${result.user_name}'s profile`)
      setSelectedNode(null)
      setShowImportDialog(false)

      const parts = []
      if (result.server_count > 0) parts.push(`${result.server_count} server${result.server_count !== 1 ? 's' : ''}`)
      if (result.has_jumphost) parts.push('jumphost')
      if (result.has_routing) parts.push('routing rules')
      toast({ title: 'Profile imported', description: parts.join(', ') || 'Empty profile' })
    } catch {
      toast({ title: 'Import failed', description: 'Could not import user profile', variant: 'destructive' })
    }
  }, [importProfile, setNodes, setEdges, toast])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await deleteConfig.mutateAsync(id)
      if (activeConfigId === id) {
        handleNew()
      }
      toast({ title: 'Deleted', description: 'Chain config removed' })
    } catch {
      toast({ title: 'Delete failed', variant: 'destructive' })
    }
  }, [activeConfigId, deleteConfig, handleNew, toast])

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border/40 glass-subtle z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            <h2 className="text-sm font-display font-bold">Chain Editor</h2>
            <span className="px-1.5 py-0.5 text-[9px] font-medium rounded bg-primary/10 text-primary border border-primary/20">
              BETA
            </span>
          </div>
          {configName && (
            <span className="text-xs text-muted-foreground">
              — {configName}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button onClick={handleNew} className="btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5" /> New
          </button>
          <button onClick={() => setShowLoadDialog(true)} className="btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1.5">
            <FolderOpen className="w-3.5 h-3.5" /> Load
          </button>
          <button onClick={() => setShowImportDialog(true)} className="btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1.5">
            <UserCircle className="w-3.5 h-3.5" /> Import Profile
          </button>
          <button onClick={handleSave} className="btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1.5">
            <Save className="w-3.5 h-3.5" /> Save
          </button>
          <div className="w-px h-5 bg-border/40" />
          <button onClick={handleValidate} className="btn-ghost !px-3 !py-1.5 text-xs flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> Validate
          </button>
          <button
            onClick={handleExport}
            disabled={exportConfig.isPending}
            className="btn-primary !px-3 !py-1.5 text-xs flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            {exportConfig.isPending ? 'Exporting...' : 'Export'}
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        <NodePalette />

        <div className="flex-1 flex flex-col overflow-hidden">
          <Canvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            setNodes={setNodes}
            setEdges={setEdges}
            onNodeSelect={handleNodeSelect}
          />
          <ValidationPanel validation={validation} />
        </div>

        {selectedNode && (
          <PropertiesPanel
            node={selectedNode}
            servers={servers}
            onUpdate={handleNodeDataUpdate}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>

      {/* Config Preview Modal */}
      {showConfig && (
        <ConfigPreview
          config={generatedConfig}
          onClose={() => setShowConfig(false)}
        />
      )}

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="modal-overlay" onClick={() => setShowSaveDialog(false)}>
          <div className="modal-backdrop" />
          <div className="modal-content max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-sm font-semibold text-foreground mb-4">Save Chain Config</h3>
              <input
                className="input-glass mb-4"
                placeholder="Config name..."
                value={configName}
                onChange={(e) => setConfigName(e.target.value)}
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && handleSaveNew()}
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setShowSaveDialog(false)} className="btn-ghost !py-1.5 text-xs">Cancel</button>
                <button
                  onClick={handleSaveNew}
                  disabled={!configName.trim() || createConfig.isPending}
                  className="btn-primary !py-1.5 text-xs"
                >
                  {createConfig.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Load Dialog */}
      {showLoadDialog && (
        <div className="modal-overlay" onClick={() => setShowLoadDialog(false)}>
          <div className="modal-backdrop" />
          <div className="modal-content max-w-md mx-4" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-sm font-semibold text-foreground mb-4">Load Chain Config</h3>
              {savedConfigs.length === 0 ? (
                <p className="text-xs text-muted-foreground">No saved configs yet.</p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {savedConfigs.map((cfg) => (
                    <div
                      key={cfg.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-card/50 border border-border/40 hover:border-primary/30 transition-all"
                    >
                      <button
                        onClick={() => handleLoad(cfg.id)}
                        className="flex-1 text-left"
                      >
                        <div className="text-xs font-medium text-foreground">{cfg.name}</div>
                        <div className="text-[10px] text-muted-foreground">
                          {cfg.is_valid ? 'Valid' : 'Invalid'} — {new Date(cfg.updated_at).toLocaleDateString()}
                        </div>
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(cfg.id) }}
                        className="p-1.5 text-muted-foreground hover:text-red-400 rounded transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex justify-end mt-4">
                <button onClick={() => setShowLoadDialog(false)} className="btn-ghost !py-1.5 text-xs">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Import Profile Dialog */}
      {showImportDialog && (
        <div className="modal-overlay" onClick={() => setShowImportDialog(false)}>
          <div className="modal-backdrop" />
          <div className="modal-content max-w-md mx-4" onClick={e => e.stopPropagation()}>
            <div className="p-6">
              <h3 className="text-sm font-semibold text-foreground mb-1">Import from User Profile</h3>
              <p className="text-[11px] text-muted-foreground mb-4">
                Select a VPN user to import their current server config, jumphost chain, and routing rules into the editor.
              </p>
              {users.length === 0 ? (
                <p className="text-xs text-muted-foreground">No users found.</p>
              ) : (
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {(users as VPNUser[]).map((u) => (
                    <button
                      key={u.id}
                      onClick={() => handleImportProfile(u.id)}
                      disabled={importProfile.isPending}
                      className="w-full flex items-center justify-between p-3 rounded-lg bg-card/50 border border-border/40 hover:border-primary/30 transition-all text-left disabled:opacity-50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
                          <UserCircle className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                          <div className="text-xs font-medium text-foreground">{u.username}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {u.enabled ? 'Active' : 'Disabled'}
                            {u.expires_at && ` · Exp: ${new Date(u.expires_at).toLocaleDateString()}`}
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {u.sub_token ? 'Has sub' : ''}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              <div className="flex justify-end mt-4">
                <button onClick={() => setShowImportDialog(false)} className="btn-ghost !py-1.5 text-xs">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChainEditor() {
  return (
    <ReactFlowProvider>
      <ChainEditorInner />
    </ReactFlowProvider>
  )
}
