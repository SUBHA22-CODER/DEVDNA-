import { createContext, useCallback, useContext, useRef, useState } from 'react'
import ConsentModal from '../components/ConsentModal'
import { readStore, writeStore } from './storage'
import { useSettings } from './useSettings'
import { useStatus } from './useStatus'

const GemmaContext = createContext(null)

/**
 * Every Gemma call goes through `runAI(fetcher)`:
 *   1. fetcher({ preview: true })  -> the backend returns the exact evidence package
 *   2. the user reviews it in the consent dialog (unless they chose "remember for this session")
 *   3. fetcher({ consent: true })  -> the backend calls Gemma and returns validated JSON
 */
export function GemmaProvider({ children }) {
  const { settings } = useSettings()
  const status = useStatus()
  const [pending, setPending] = useState(null)
  const resolver = useRef(null)

  const askConsent = useCallback((preview, purpose) => {
    return new Promise((resolve) => {
      resolver.current = resolve
      setPending({ preview, purpose })
    })
  }, [])

  const close = (decision, remember) => {
    if (decision && remember) writeStore('devdna.consent', true, 'session')
    setPending(null)
    resolver.current?.(decision)
  }

  const runAI = useCallback(
    async (fetcher, purpose) => {
      const preview = await fetcher({ preview: true })
      if (!preview.configured) {
        const err = { code: 'not_configured', message: 'Gemma is not configured. Add GEMINI_API_KEY to backend/.env and restart the backend (see Settings).' }
        throw err
      }
      const remembered = settings.consentMode === 'session' && readStore('devdna.consent', false, 'session')
      const ok = remembered || (await askConsent(preview, purpose))
      if (!ok) throw { code: 'cancelled', message: 'Request cancelled. Nothing was sent.' }
      const result = await fetcher({ consent: true })
      status?.refresh?.()
      return result
    },
    [askConsent, settings.consentMode, status],
  )

  return (
    <GemmaContext.Provider value={{ runAI }}>
      {children}
      <ConsentModal
        open={Boolean(pending)}
        preview={pending?.preview}
        purpose={pending?.purpose}
        sessionOption={settings.consentMode === 'session'}
        onCancel={() => close(false)}
        onConfirm={(remember) => close(true, remember)}
      />
    </GemmaContext.Provider>
  )
}

export function useGemma() {
  return useContext(GemmaContext)
}
