import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store'
import { ToastProvider } from './components/Toast'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'

import Landing    from './pages/Landing'
import Auth       from './pages/Auth'
import Upload     from './pages/patient/Upload'
import Results    from './pages/patient/Results'
import Home       from './pages/patient/Home'
import Dashboard  from './pages/doctor/Dashboard'
import CaseReview from './pages/doctor/CaseReview'
import Report     from './pages/doctor/Report'

export default function App() {
  const { user } = useAuthStore()

  return (
    <ToastProvider>
      {/* Light ambient background blobs */}
      <div className="orb orb-1" aria-hidden="true" />
      <div className="orb orb-2" aria-hidden="true" />

      <div className="relative min-h-screen bg-gray-50">
        <Navbar />

        <main className="relative z-10 pt-16">
          <Routes>
            {/* Landing */}
            <Route path="/" element={user
              ? <Navigate to={user.role === 'doctor' ? '/doctor' : '/upload'} replace />
              : <Landing />}
            />

            {/* Auth */}
            <Route path="/login"    element={<Auth mode="login" />} />
            <Route path="/register" element={<Auth mode="register" />} />

            {/* Patient */}
            <Route path="/upload"  element={<ProtectedRoute requireRole="patient"><Upload /></ProtectedRoute>} />
            <Route path="/results/:caseId" element={<ProtectedRoute requireRole="patient"><Results /></ProtectedRoute>} />
            <Route path="/history" element={<ProtectedRoute requireRole="patient"><Home /></ProtectedRoute>} />

            {/* Doctor */}
            <Route path="/doctor" element={<ProtectedRoute requireRole="doctor"><Dashboard /></ProtectedRoute>} />
            <Route path="/doctor/cases/:caseId" element={<ProtectedRoute requireRole="doctor"><CaseReview /></ProtectedRoute>} />
            <Route path="/doctor/cases/:caseId/report" element={<ProtectedRoute requireRole="doctor"><Report /></ProtectedRoute>} />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  )
}
