import { useQuery } from '@tanstack/react-query'
import animationsApi, { type AnimationDto } from '../api/animations.api'

const STALE_MS = 10 * 60 * 1000 // 10 min — animations rarely change

export function useAnimations() {
  return useQuery<AnimationDto[]>({
    queryKey: ['vtf-animations'],
    queryFn: () => animationsApi.getAnimations(),
    staleTime: STALE_MS,
  })
}
