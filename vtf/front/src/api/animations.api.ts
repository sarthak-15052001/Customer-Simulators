import apiClient from './client'
import { ENDPOINTS } from './endpoints'

export type AnimationDto = {
  id?: string
  nom: string
  note?: string
  icon?: string
}

function unwrap(data: unknown): AnimationDto[] {
  if (Array.isArray(data)) return data as AnimationDto[]
  if (data && typeof data === 'object') {
    const o = data as Record<string, unknown>
    if (Array.isArray(o.data)) return o.data as AnimationDto[]
  }
  return []
}

export const animationsApi = {
  getAnimations: async (): Promise<AnimationDto[]> => {
    const { data } = await apiClient.get<unknown>(ENDPOINTS.ANIMATIONS)
    return unwrap(data)
  },
}

export default animationsApi
