import axios from 'axios'
import type { CohortFilters, FormSettings, MetricsResponse, SavedCohort, User } from '../types'

export interface SurveySummary { id: string; title: string; completions: number }
export interface SurveyQuestion { key: string; text: string; type: string }
export interface SurveyCrosstab {
  paired_completions: number
  x_n?: number
  y_n?: number
  x_values: string[]
  y_values: string[]
  cells: { x: string; y: string; count: number; pct: number }[]
  x_option_counts?: Record<string, number>
  y_option_counts?: Record<string, number>
  numeric_summaries?: {
    axis: 'x' | 'y'
    groups: { label: string; n: number; mean: number; sd: number | null }[]
  }[]
}

// The CSRF cookie's name. Configurable at build time because PRism may share a
// host with another Django app that sets its own `csrftoken`; the backend's
// CSRF_COOKIE_NAME must match.
const CSRF_COOKIE_NAME: string = import.meta.env.VITE_CSRF_COOKIE_NAME || 'csrftoken'

// Anchored to a cookie boundary, so `csrftoken` never matches the tail of
// another cookie's name (e.g. `prism_csrftoken`), and vice versa.
export function getCsrfToken(cookie: string = document.cookie, name: string = CSRF_COOKIE_NAME): string {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${escaped}=([^;]+)`))
  return match ? match[1] : ''
}

// BASE_URL is Vite's `base`: '/' normally, '/analytics/' when PRism is served
// under a path prefix (see vite.config.ts). It always ends with '/'.
const api = axios.create({
  baseURL: `${import.meta.env.BASE_URL}api`,
  withCredentials: true,
})

api.interceptors.request.use(config => {
  const token = getCsrfToken()
  if (token) {
    config.headers['X-CSRFToken'] = token
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error.config?.url ?? ''
    const status: number = error.response?.status
    // On 401 (session expired) from non-auth endpoints, reload so useAuth
    // re-checks and shows LoginPage. 403 means "authorised but forbidden"
    // (e.g. non-Premium hitting export) — do NOT reload; let the caller handle it.
    if (status === 401 && !url.includes('/auth/')) {
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

function toParams(filters: CohortFilters): URLSearchParams {
  const p = new URLSearchParams()
  for (const [key, val] of Object.entries(filters)) {
    if (val === undefined || val === null || val === '') continue
    if (Array.isArray(val)) {
      val.forEach(v => p.append(key, String(v)))
    } else {
      p.set(key, String(val))
    }
  }
  return p
}

export async function fetchFormSettings(disease: string, org?: string): Promise<FormSettings> {
  const params = new URLSearchParams({ disease })
  if (org) params.set('org', org)
  const { data } = await api.get<FormSettings>(`/form-settings/?${params}`)
  return data
}

export async function fetchMetrics(filters: CohortFilters): Promise<MetricsResponse> {
  const { data } = await api.get<MetricsResponse>(`/metrics/?${toParams(filters)}`)
  return data
}

export async function fetchSurveys(): Promise<SurveySummary[]> {
  const { data } = await api.get<SurveySummary[]>('/surveys/')
  return data
}

export async function fetchSurveyQuestions(id: string): Promise<SurveyQuestion[]> {
  const { data } = await api.get<SurveyQuestion[]>(`/surveys/${id}/questions/`)
  return data
}

export async function fetchSurveyCrosstab(id: string, x: string, y: string, includePartial = false): Promise<SurveyCrosstab> {
  const params = new URLSearchParams({ x, y })
  if (includePartial) params.set('include_partial', 'true')
  const { data } = await api.get<SurveyCrosstab>(`/surveys/${id}/crosstab/?${params}`)
  return data
}

export interface SurveyResponseOption { label: string; count: number; pct: number }
export interface SurveyResponseQuestion { key: string; text: string; n: number; options: SurveyResponseOption[] }
export interface SurveyResponsesData { total_responses: number; include_partial: boolean; questions: SurveyResponseQuestion[] }

export async function fetchSurveyResponses(id: string, includePartial = false): Promise<SurveyResponsesData> {
  const params = new URLSearchParams()
  if (includePartial) params.set('include_partial', 'true')
  const { data } = await api.get<SurveyResponsesData>(`/surveys/${id}/responses/?${params}`)
  return data
}

export interface SurveyResponseExportRow { respondent_id: string; email?: string; answers: Record<string, string> }
export interface SurveyResponseExport {
  questions: { key: string; text: string }[]
  rows: SurveyResponseExportRow[]
  truncated: boolean
}

export async function fetchSurveyResponsesExport(id: string, includePartial = false, includeEmail = false): Promise<SurveyResponseExport> {
  const params = new URLSearchParams()
  if (includePartial) params.set('include_partial', 'true')
  if (includeEmail) params.set('include_email', 'true')
  const { data } = await api.get<SurveyResponseExport>(`/surveys/${id}/responses/export/?${params}`)
  return data
}

// Auth
export async function fetchCurrentUser() {
  const { data } = await api.get('/auth/user/')
  return data
}

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login/', { email, password })
  return data
}

export async function logout() {
  await api.post('/auth/logout/')
}

export type SignupResult =
  | { created: true; user: User }
  // An account already exists for the address; a setup link may have been emailed.
  | { created: false; detail: string }

export async function signup(email: string, password: string, name: string): Promise<SignupResult> {
  const { status, data } = await api.post('/auth/signup/', { email, password, name })
  return status === 201 ? { created: true, user: data } : { created: false, detail: data.detail }
}

export async function fetchAuthConfig(): Promise<{ signup_enabled: boolean }> {
  const { data } = await api.get<{ signup_enabled: boolean }>('/auth/config/')
  return data
}

export async function requestPasswordReset(email: string) {
  const { data } = await api.post('/auth/password-reset/', { email })
  return data
}

export async function confirmPasswordReset(token: string, password: string) {
  const { data } = await api.post('/auth/password-reset/confirm/', { token, password })
  return data
}

export async function fetchOrganizations(): Promise<string[]> {
  const { data } = await api.get<string[]>('/auth/organizations/')
  return data
}

export async function fetchMyOrgs(): Promise<{ value: string; label: string }[]> {
  const { data } = await api.get<{ value: string; label: string }[]>('/auth/my-orgs/')
  return data
}

// Saved cohorts
export async function fetchSavedCohorts(): Promise<SavedCohort[]> {
  const { data } = await api.get<SavedCohort[]>('/cohorts/saved/')
  return data
}

export async function createSavedCohort(payload: { name: string; description: string; filters: CohortFilters }): Promise<SavedCohort> {
  const { data } = await api.post<SavedCohort>('/cohorts/saved/', payload)
  return data
}

export async function updateSavedCohort(id: number, payload: { name?: string; description?: string; filters?: CohortFilters }): Promise<SavedCohort> {
  const { data } = await api.put<SavedCohort>(`/cohorts/saved/${id}/`, payload)
  return data
}

export async function deleteSavedCohort(id: number): Promise<void> {
  await api.delete(`/cohorts/saved/${id}/`)
}

export default api
