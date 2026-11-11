/** Regimen name without its parenthetical drug list: "VRd (bortezomib, …)" → "VRd". */
export function shortTherapyName(name: string): string {
  return name.split(' (')[0]
}
