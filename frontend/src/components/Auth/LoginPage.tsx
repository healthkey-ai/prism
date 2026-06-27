import { useState, useEffect } from 'react'
import type { AuthState } from '../../hooks/useAuth'
import { fetchOrganizations } from '../../api/client'

interface Props {
  auth: AuthState
}

export default function LoginPage({ auth }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [organization, setOrganization] = useState('')
  const [organizations, setOrganizations] = useState<string[]>([])
  const [orgsLoading, setOrgsLoading] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (mode === 'signup') {
      setOrgsLoading(true)
      fetchOrganizations()
        .then(orgs => {
          setOrganizations(orgs)
          // Default to ABC Foundation; fall back to first org if absent
          const defaultOrg = orgs.includes('ABC Foundation') ? 'ABC Foundation' : (orgs[0] ?? '')
          setOrganization(defaultOrg)
        })
        .catch(() => setOrganizations([]))
        .finally(() => setOrgsLoading(false))
    }
  }, [mode])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await auth.login(email, password)
      } else {
        await auth.signup(email, password, name, organization)
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">Analytics Platform</h1>
          <p className="text-slate-400 text-sm mt-1">Real-world evidence for oncology research</p>
        </div>

        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-5">
          <div className="flex rounded-lg border border-slate-700 p-0.5 bg-slate-900/50">
            {(['login', 'signup'] as const).map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); setConfirmPassword('') }}
                className={`flex-1 py-2 text-sm font-semibold rounded-md transition-colors ${
                  mode === m ? 'bg-teal-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {m === 'login' ? 'Sign In' : 'Sign Up'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs text-slate-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
              />
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
              />
            </div>

            {mode === 'signup' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
                />
              </div>
            )}

            {mode === 'signup' && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Organization <span className="text-slate-500">(optional)</span>
                </label>
                {orgsLoading ? (
                  <p className="text-xs text-slate-400">Loading organizations…</p>
                ) : organizations.length === 0 ? (
                  <p className="text-xs text-slate-400">No organizations available — contact your administrator</p>
                ) : (
                  <select
                    value={organization}
                    onChange={e => setOrganization(e.target.value)}
                    className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-teal-500"
                  >
                    <option value="">No organization</option>
                    {organizations.map(org => (
                      <option key={org} value={org}>{org}</option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {error && (
              <p className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
            >
              {submitting ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
