import client from './client'
import type { AuthUser } from '../store'

export interface TokenResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export const registerApi = (email: string, password: string, full_name: string, consent_given: boolean) =>
  client.post<TokenResponse>('/auth/register', { email, password, full_name, consent_given }).then(r => r.data)

export const loginApi = (email: string, password: string) =>
  client.post<TokenResponse>('/auth/login', { email, password }).then(r => r.data)
