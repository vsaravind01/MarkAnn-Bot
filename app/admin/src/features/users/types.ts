export interface UserOut {
  id: number
  email: string
  first_name: string
  last_name: string
  role: 'trader' | 'admin' | 'superuser'
  is_active: boolean
  created_at: string | null
}

export interface PaginatedUsers {
  items: UserOut[]
  total: number
  page: number
  page_size: number
}
