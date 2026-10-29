import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, it, expect, beforeEach } from 'vitest'

// Stub every chart sub-component so the Dashboard header renders without
// needing a complete metrics fixture.
vi.mock('../../charts/ResponseRates', () => ({ default: () => null }))
vi.mock('../../charts/TreatmentPatterns', () => ({ default: () => null }))
vi.mock('../../charts/TreatmentLines', () => ({ default: () => null }))
vi.mock('../../charts/Demographics', () => ({ default: () => null }))
vi.mock('../../charts/StagingPanel', () => ({ default: () => null }))
vi.mock('../../charts/LabsPanel', () => ({ default: () => null }))
vi.mock('../../charts/TreatmentDuration', () => ({ default: () => null }))
vi.mock('../../charts/Sequences', () => ({ default: () => null }))
vi.mock('../../charts/SurvivalCurves', () => ({ default: () => null }))
vi.mock('../../charts/TTNT', () => ({ default: () => null }))
vi.mock('../../charts/Switching', () => ({ default: () => null }))
vi.mock('../../charts/SubgroupSurvival', () => ({ default: () => null }))
vi.mock('../../charts/PathwaySunburst', () => ({ default: () => null }))
vi.mock('../../charts/DurationOfResponse', () => ({ default: () => null }))
vi.mock('../../charts/TreatmentSankey', () => ({ default: () => null }))
vi.mock('../../charts/ForestPlot', () => ({ default: () => null }))
vi.mock('../../charts/CohortCharacterization', () => ({ default: () => null }))
vi.mock('../../charts/IncidenceChart', () => ({ default: () => null }))
vi.mock('../../charts/TimeToTreatment', () => ({ default: () => null }))
vi.mock('../../charts/DiseaseStateSnapshot', () => ({ default: () => null }))
vi.mock('../../charts/EligibilityFunnel', () => ({ default: () => null }))
vi.mock('../../charts/TherapyCategories', () => ({ default: () => null }))
vi.mock('../../charts/PathwayOutcomes', () => ({ default: () => null }))
vi.mock('../../charts/Pod24', () => ({ default: () => null }))
vi.mock('../../charts/LandmarkResponse', () => ({ default: () => null }))
vi.mock('../../charts/TransformationChart', () => ({ default: () => null }))
vi.mock('../Surveys', () => ({ default: () => null }))
vi.mock('../../ui/MetricCard', () => ({ default: ({ children }: { children?: React.ReactNode }) => <>{children}</> }))

import Dashboard from '..'
import api from '../../../api/client'

vi.mock('../../../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../../../api/client')>()
  return { ...mod, default: { get: vi.fn() } }
})

const STAFF_USER = {
  id: 1, email: 'staff@example.com', name: 'Staff',
  is_staff: true, is_premium: false, role: null, is_org_admin: false,
}

// null triggers !metrics === true so all *HasContent flags are true and all
// tabs are visible without needing a complete data fixture.
const MINIMAL_METRICS = null as never

beforeEach(() => vi.clearAllMocks())

it('Export button calls /export/ with cohort_characterization without requiring a saved cohort', async () => {
  const user = userEvent.setup()
  vi.mocked(api.get).mockResolvedValue({
    data: new Blob(['id,age\n1,55'], { type: 'text/csv' }),
    headers: {},
  })
  URL.createObjectURL = vi.fn(() => 'blob:test')
  URL.revokeObjectURL = vi.fn()

  render(
    <Dashboard
      metrics={MINIMAL_METRICS}
      loading={false}
      disease="Multiple Myeloma"
      user={STAFF_USER as never}
      onLogout={vi.fn()}
      filters={{}}
      // activeSavedCohortId intentionally omitted
    />
  )

  const btn = await screen.findByTitle('Export cohort as CSV')
  await user.click(btn)

  await waitFor(() => {
    const exportCall = vi.mocked(api.get).mock.calls.find(([url]) =>
      String(url).includes('/export/')
    )
    expect(exportCall).toBeDefined()
    expect(String(exportCall![0])).toContain('chart=cohort_characterization')
    expect(String(exportCall![0])).toContain('file_format=csv')
  })
  expect(URL.createObjectURL).toHaveBeenCalledOnce()
})
