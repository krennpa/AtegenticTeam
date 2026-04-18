import type {
  PreferenceQuestionCatalogResponse,
  ProfilePreferenceEvent,
  ProfilePreferenceEventCreate,
  ProfilePreferenceProgress,
  TeamPreferenceSnapshot,
} from './types'

export type ApiClient = {
  get: <T>(path: string) => Promise<T>
  post: <T>(path: string, body?: unknown) => Promise<T>
  put: <T>(path: string, body?: unknown) => Promise<T>
  delete: <T>(path: string) => Promise<T>
  getPreferenceQuestions: (limit?: number) => Promise<PreferenceQuestionCatalogResponse>
  submitPreferenceEvent: (payload: ProfilePreferenceEventCreate) => Promise<ProfilePreferenceEvent>
  getPreferenceProgress: () => Promise<ProfilePreferenceProgress>
  getTeamPreferences: (teamId: string) => Promise<TeamPreferenceSnapshot>
  rebuildTeamPreferences: (teamId: string) => Promise<TeamPreferenceSnapshot>
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
const DEFAULT_PREFERENCE_EVENT_SOURCE = 'user_gameplay'

export function createApiClient(
  getToken: () => string | null,
  onUnauthorized?: () => void
): ApiClient {
  async function request<T>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T> {
    const token = getToken()
    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: method === 'GET' || method === 'DELETE' ? undefined : JSON.stringify(body ?? {}),
    })
    if (!res.ok) {
      const text = await res.text()
      if (res.status === 401 && token) {
        onUnauthorized?.()
      }
      throw new Error(text || `Request failed: ${res.status}`)
    }
    if (res.status === 204) return undefined as unknown as T
    return res.json() as Promise<T>
  }

  return {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
    put: (path, body) => request('PUT', path, body),
    delete: (path) => request('DELETE', path),
    getPreferenceQuestions: (limit = 5) => request('GET', `/profiles/me/preference-questions?limit=${limit}`),
    submitPreferenceEvent: (payload) => {
      const normalizedPayload: ProfilePreferenceEventCreate = {
        ...payload,
        weight: payload.weight ?? 1.0,
        source: payload.source ?? DEFAULT_PREFERENCE_EVENT_SOURCE,
      }
      return request('POST', '/profiles/me/preference-events', normalizedPayload)
    },
    getPreferenceProgress: () => request('GET', '/profiles/me/preference-progress'),
    getTeamPreferences: (teamId) => request('GET', `/teams/${teamId}/preferences`),
    rebuildTeamPreferences: (teamId) => request('POST', `/teams/${teamId}/preferences/rebuild`, {}),
  }
}
