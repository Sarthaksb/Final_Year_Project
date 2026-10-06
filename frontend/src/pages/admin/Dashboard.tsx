import { useEffect, useState } from 'react'
import { getAnalytics, getAuditLogs, AnalyticsData, AuditLog } from '../../api/admin'
import { useToast } from '../../components/Toast'
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#a855f7', '#ec4899', '#f43f5e']

export default function AdminDashboard() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  useEffect(() => {
    Promise.all([getAnalytics(), getAuditLogs(50)])
      .then(([a, logs]) => {
        setAnalytics(a)
        setAuditLogs(logs)
      })
      .catch(() => toast.error('Failed to load admin dashboard data.'))
      .finally(() => setLoading(false))
  }, [toast])

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-gray-50">
        <div className="w-12 h-12 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
      </div>
    )
  }

  if (!analytics) return <div className="p-12 text-center">Failed to load data.</div>

  return (
    <div className="min-h-[calc(100vh-64px)] py-12 px-6 bg-gray-50">
      <div className="max-w-7xl mx-auto space-y-8 page-enter">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Hospital Admin Dashboard</h1>
          <div className="flex gap-4">
            <div className="bg-white px-4 py-2 rounded-xl shadow-sm border border-gray-200 text-center">
              <p className="text-xs text-gray-500 uppercase font-bold">Total Cases</p>
              <p className="text-xl font-black text-brand-600">{analytics.total_cases}</p>
            </div>
            <div className="bg-white px-4 py-2 rounded-xl shadow-sm border border-gray-200 text-center">
              <p className="text-xs text-gray-500 uppercase font-bold">Avg Review Time</p>
              <p className="text-xl font-black text-brand-600">{analytics.avg_review_time_hours.toFixed(1)}h</p>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Chart 1: Cases per day */}
          <div className="bg-white p-6 rounded-2xl shadow-card border border-gray-200">
            <h3 className="font-bold text-gray-900 mb-6">Cases Per Day</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={analytics.cases_per_day}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#9ca3af' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#9ca3af' }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="cases" stroke="#4f46e5" strokeWidth={3} dot={{ r: 4, fill: '#4f46e5' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Urgency Distribution */}
          <div className="bg-white p-6 rounded-2xl shadow-card border border-gray-200">
            <h3 className="font-bold text-gray-900 mb-6">Urgency Distribution</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={analytics.urgency_distribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} fill="#8884d8" label>
                    {analytics.urgency_distribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 3: AI-vs-Doctor Agreement */}
          <div className="bg-white p-6 rounded-2xl shadow-card border border-gray-200">
            <h3 className="font-bold text-gray-900 mb-6">AI vs Doctor Agreement</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={analytics.agreement} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={80} fill="#8884d8" label>
                    <Cell fill="#10b981" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 4: Override Rate per Class */}
          <div className="bg-white p-6 rounded-2xl shadow-card border border-gray-200">
            <h3 className="font-bold text-gray-900 mb-6">Overrides by Class</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics.override_per_class}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#9ca3af' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#9ca3af' }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Audit Logs Table */}
        <div className="bg-white rounded-2xl shadow-card border border-gray-200 overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-gray-50">
            <h3 className="font-bold text-gray-900">Recent Audit Logs</h3>
            <span className="text-xs text-gray-500">Last 50 actions</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-white text-gray-400 font-medium text-xs uppercase">
                <tr>
                  <th className="px-6 py-4">Timestamp</th>
                  <th className="px-6 py-4">User</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4">Action</th>
                  <th className="px-6 py-4">Case ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {auditLogs.map((log) => (
                  <tr key={log._id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 whitespace-nowrap text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-3 font-medium text-gray-900">{log.user_email}</td>
                    <td className="px-6 py-3">
                      <span className="px-2 py-1 rounded text-xs font-bold bg-gray-100 text-gray-600">{log.user_role}</span>
                    </td>
                    <td className="px-6 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${log.action === 'view' ? 'bg-blue-50 text-blue-600' : 'bg-amber-50 text-amber-600'}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-3 font-mono text-gray-500 text-xs">{log.case_id}</td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-400">No audit logs found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
