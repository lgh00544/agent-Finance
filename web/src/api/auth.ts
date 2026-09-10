import { get, post } from './client'

export type AuthStatus = {
  multi_user_enabled: boolean
  user_id: number | null
  username: string | null
  role: 'admin' | 'researcher' | 'viewer' | null
}

export type LoginResult = {
  id: number
  username: string
  role: AuthStatus['role']
  access_token: string
  token_type: string
}

export const authStatus = (): Promise<AuthStatus> => get('/auth/status')
export const login = (username: string, password: string): Promise<LoginResult> =>
  post('/auth/login', { username, password })
export const register = (username: string, password: string): Promise<LoginResult> =>
  post('/auth/register', { username, password })
