import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Run an async function and track { data, error, loading }.
 * `deps` re-run it; `reload()` runs it again on demand.
 */
export function useAsync(fn, deps = [], { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled })
  const mounted = useRef(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const run = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fnRef.current()
      if (mounted.current) setState({ data, error: null, loading: false })
      return data
    } catch (error) {
      if (mounted.current) setState((s) => ({ ...s, error, loading: false }))
      return null
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    if (enabled) run()
    return () => {
      mounted.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled])

  const setData = useCallback((updater) => {
    setState((s) => ({ ...s, data: typeof updater === 'function' ? updater(s.data) : updater }))
  }, [])

  return { ...state, reload: run, setData }
}

/** Call `fn` every `ms` while `active` is true. */
export function usePoll(fn, ms, active) {
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    if (!active) return undefined
    let stopped = false
    let timer
    const tick = async () => {
      try {
        await fnRef.current()
      } finally {
        if (!stopped) timer = setTimeout(tick, ms)
      }
    }
    timer = setTimeout(tick, ms)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [ms, active])
}
