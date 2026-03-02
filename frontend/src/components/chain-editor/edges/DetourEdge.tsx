import { memo } from 'react'
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react'

function DetourEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 16,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: selected ? 'hsl(187, 85%, 53%)' : 'hsl(228, 8%, 24%)',
          strokeWidth: selected ? 2.5 : 2,
          filter: selected ? 'drop-shadow(0 0 4px hsla(187, 85%, 53%, 0.3))' : 'none',
        }}
      />
      {/* Animated dot along the path */}
      <circle r="3" fill="hsl(187, 85%, 53%)" opacity={0.7}>
        <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
      </circle>
    </>
  )
}

export default memo(DetourEdge)
