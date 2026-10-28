import api, { getCsrfToken } from '../client'

describe('getCsrfToken', () => {
  it('reads the default csrftoken cookie', () => {
    expect(getCsrfToken('sessionid=abc; csrftoken=TOKEN1', 'csrftoken')).toBe('TOKEN1')
  })

  it('reads a cookie at the start of the string', () => {
    expect(getCsrfToken('csrftoken=TOKEN1; other=x', 'csrftoken')).toBe('TOKEN1')
  })

  it('does not match the tail of another cookie name', () => {
    // A host shared with another Django app: PRism's cookie is prism_csrftoken,
    // the other app's is csrftoken. Each name must find only its own value.
    const cookie = 'prism_csrftoken=PRISM; csrftoken=OTHER'
    expect(getCsrfToken(cookie, 'csrftoken')).toBe('OTHER')
    expect(getCsrfToken(cookie, 'prism_csrftoken')).toBe('PRISM')
  })

  it('returns an empty string when the cookie is absent', () => {
    expect(getCsrfToken('sessionid=abc', 'csrftoken')).toBe('')
    expect(getCsrfToken('', 'csrftoken')).toBe('')
  })

  it('treats regex characters in the name literally', () => {
    expect(getCsrfToken('a.b=1; aXb=2', 'a.b')).toBe('1')
  })
})

describe('api client', () => {
  it('builds its base URL from Vite BASE_URL', () => {
    expect(api.defaults.baseURL).toBe(`${import.meta.env.BASE_URL}api`)
  })

  it('is /api when no base path is set', () => {
    expect(import.meta.env.BASE_URL).toBe('/')
    expect(api.defaults.baseURL).toBe('/api')
  })
})
