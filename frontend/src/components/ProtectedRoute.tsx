import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store'

interface Props {
  children: React.ReactNode
  requireRole?: 'patient' | 'doctor'
}

/**
 * Wraps routes that require authentication.
 * - If no token: redirect to /login
 * - If requireRole set and role doesn't match: redirect to their home
 */
export default function ProtectedRoute({ children, requireRole }: Props) {
  const { token, user } = useAuthStore()

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (requireRole && user.role !== requireRole) {
    // Doctor trying to access patient routes → go to doctor dashboard
    // Patient trying to access doctor routes → go to patient home
    const redirect = user.role === 'doctor' ? '/doctor' : '/upload'
    return <Navigate to={redirect} replace />
  }

  return <>{children}</>
}
