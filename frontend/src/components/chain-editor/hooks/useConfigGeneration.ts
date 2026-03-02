import { useExportChainConfig, useValidateGraph } from '@/api/chain-configs'

export function useConfigGeneration() {
  const validateMutation = useValidateGraph()
  const exportMutation = useExportChainConfig()

  return {
    validate: validateMutation,
    exportConfig: exportMutation,
    isExporting: exportMutation.isPending,
    isValidating: validateMutation.isPending,
  }
}
