export type ApiClient = {
  get: <T>(path: string) => Promise<T>
  post: <T>(path: string, body?: unknown) => Promise<T>
  put: <T>(path: string, body?: unknown) => Promise<T>
  delete: <T>(path: string) => Promise<T>
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export function createApiClient(getToken: () => string | null): ApiClient {
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
  }
}
