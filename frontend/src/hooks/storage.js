// Browser storage can be unavailable (private mode, blocked cookies). Never let it break the app.

export function readStore(key, fallback, store = 'local') {
  try {
    const s = store === 'session' ? window.sessionStorage : window.localStorage
    const v = s.getItem(key)
    return v === null ? fallback : JSON.parse(v)
  } catch {
    return fallback
  }
}

export function writeStore(key, value, store = 'local') {
  try {
    const s = store === 'session' ? window.sessionStorage : window.localStorage
    if (value === null || value === undefined) s.removeItem(key)
    else s.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}
