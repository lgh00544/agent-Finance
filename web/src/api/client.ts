import axios from 'axios'

/** 409 状态冲突（已有同类任务 / 状态不允许操作）——供 React Query onError 区分展示 */
export class ConflictError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ConflictError'
  }
}

/** GET/PUT 默认 60s 超时 */
const api = axios.create({ baseURL: '/api', timeout: 60_000 })
/** POST 默认 600s（后台任务长耗时） */
const apiPost = axios.create({ baseURL: '/api', timeout: 600_000 })
/** OCR 上传 180s */
const apiOcr = axios.create({ baseURL: '/api', timeout: 180_000 })
/** chat_learn 上传 60s */
const apiUpload = axios.create({ baseURL: '/api', timeout: 60_000 })

function toErr(err: unknown): Error {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (status === 409) return new ConflictError(typeof detail === 'string' ? detail : '状态冲突：操作不允许')
    if (err.response) return new Error(typeof detail === 'string' ? detail : `请求失败（HTTP ${status}）`)
    return new Error('网络错误：无法连接后端服务')
  }
  return err instanceof Error ? err : new Error(String(err))
}

async function request<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    const res = await fn()
    return res.data
  } catch (err) {
    throw toErr(err)
  }
}

export function get<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T> {
  return request(() => api.get(path, { params }))
}

export function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request(() => apiPost.post(path, body ?? {}))
}

export function put<T = unknown>(path: string, body?: unknown): Promise<T> {
  return request(() => api.put(path, body ?? {}))
}

/** multipart 上传（OCR / chat_learn） */
export function upload<T = unknown>(
  path: string,
  file: Blob,
  filename: string,
  params?: Record<string, unknown>,
  data?: Record<string, unknown>,
  timeoutMs = 180_000,
): Promise<T> {
  const form = new FormData()
  form.append('file', file, filename)
  if (data) {
    for (const [k, v] of Object.entries(data)) form.append(k, String(v))
  }
  const inst = timeoutMs >= 120_000 ? apiOcr : apiUpload
  return request(() => inst.post(path, form, { params }))
}

/** 上传用常量（OCR 180s / chat_learn 60s） */
export const UPLOAD_OCR_TIMEOUT = 180_000
export const UPLOAD_CHAT_TIMEOUT = 60_000
