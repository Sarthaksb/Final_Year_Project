import client from './client'

export interface AuditLog {
  _id: string
  user_id: string
  user_email: string
  user_role: string
  action: string
  case_id: string
  timestamp: string
}

export interface AnalyticsData {
  cases_per_day: { date: string; cases: number }[]
  urgency_distribution: { name: string; value: number }[]
  agreement: { name: string; value: number }[]
  override_per_class: { name: string; value: number }[]
  avg_review_time_hours: number
  total_cases: number
  total_overrides: number
}

export const getAnalytics = async () =>
  client.get<AnalyticsData>('/admin/analytics').then(r => r.data)

export const getAuditLogs = async (limit = 100) =>
  client.get<AuditLog[]>('/admin/audit', { params: { limit } }).then(r => r.data)
