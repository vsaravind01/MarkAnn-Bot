export interface AuthUser {
  id: number
  email: string
  role: 'trader' | 'admin' | 'superuser'
  first_name: string
  last_name: string
  is_active: boolean
  created_at?: string
}
