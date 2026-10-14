import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '../services/api'

const StatusContext = createContext(null)

/** Polls backend health and AI configuration so every page can show honest status. */
export function StatusProvider({ children }) {
  const [status, setStatus] = useState({ backend: 'checking', health: null, ai: null })

  const refresh = useCallback(async (check = false) => {
    try {
      const [health, ai] = await Promise.all([api.health(), api.aiStatus(check)])
      setStatus({ backend: 'online', health, ai })
      return ai
    } catch {
      setStatus((s) => ({ ...s, backend: 'offline' }))
      return null
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(() => refresh(), 30000)
    return () => clearInterval(t)
  }, [refresh])

  return <StatusContext.Provider value={{ ...status, refresh }}>{children}</StatusContext.Provider>
}

export function useStatus() {
  return useContext(StatusContext)
}
