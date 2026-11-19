import type { KMOption } from './KMCompare'

export const SURVIVAL_OPTIONS: KMOption[] = [
  { key: 'os',  label: 'OS',  pick: m => m.survival?.os },
  { key: 'pfs', label: 'PFS', pick: m => m.survival?.pfs },
  { key: 'efs', label: 'EFS', pick: m => m.survival?.efs },
]

export const LANDMARK_OPTIONS: KMOption[] = [
  { key: 'landmark', label: 'Landmark OS', pick: m => m.landmark_survival },
]

export const DOR_OPTIONS: KMOption[] = [
  { key: 'first_line',  label: '1st Line', pick: m => m.dor?.first_line },
  { key: 'second_line', label: '2nd Line', pick: m => m.dor?.second_line },
]

export const TTNT_OPTIONS: KMOption[] = [
  { key: 'line_1_to_2', label: '1L → 2L', pick: m => m.ttnt?.line_1_to_2 },
  { key: 'line_2_to_3', label: '2L → 3L', pick: m => m.ttnt?.line_2_to_3 },
]
