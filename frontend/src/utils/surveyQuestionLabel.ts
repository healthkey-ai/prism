/** "Q7a. How …" when the question carries a questionnaire number, else the bare text. */
export function questionLabel(q: { number?: string | null; text: string }): string {
  return q.number ? `Q${q.number}. ${q.text}` : q.text
}
