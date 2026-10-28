import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, it, expect, beforeEach } from 'vitest'
import Dashboard from '..'
import api from '../../../api/client'

vi.mock('../../../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../../../api/client')>()
  return { ...mod, default: { get: vi.fn() } }
})

const STAFF_USER = { id: 1, email: 'staff@example.com', name: 'Staff', is_staff: true, is_premium: false, role: null, is_org_admin: false }
const BASE_METRICS = {
  cohort: { count: 5 },
  eligibility: null, cohort_characterization: null, disease_state: null,
  survival: null, subgroup_survival: null, landmark_survival: null,
  response_rates: null, pod24: null, landmark_response: null,
  pathway_outcomes: null, transformation: null, dor: null,
  forest_plot: null, pathway_sunburst: null, treatment_patterns: null,
  staging: null, demographics: null, labs: null, ttnt: null,
  switching: null,
}

beforeEach(() => vi.clearAllMocks())

it('Export button calls /export/ with cohort_characterization and no saved cohort required', async () => {
  const user = userEvent.setup()
  vi.mocked(api.get).mockResolvedValue({
    data: new Blob(['id,age\n1,55'], { type: 'text/csv' }),
    headers: {},
  })
  URL.createObjectURL = vi.fn(() => 'blob:test')
  URL.revokeObjectURL = vi.fn()

  render(
    <Dashboard
      metrics={BASE_METRICS as never}
      loading={false}
      disease="Multiple Myeloma"
      user={STAFF_USER as never}
      onLogout={vi.fn()}
      filters={{}}
      // activeSavedCohortId intentionally omitted — export must work without it
    />
  )

  await user.click(screen.getByTitle('Export cohort as CSV'))

  await waitFor(() => {
    const call = vi.mocked(api.get).mock.calls.find(([url]) => String(url).includes('/export/'))
    expect(call).toBeDefined()
    expect(String(call![0])).toContain('chart=cohort_characterization')
    expect(String(call![0])).toContain('file_format=csv')
  })
  expect(URL.createObjectURL).toHaveBeenCalledOnce()
})
