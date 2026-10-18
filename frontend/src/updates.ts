// Live updates: the server sends an event whenever a trace changes, so the
// shown data is reloaded without pressing refresh. See
// src/governancekit/server/updates.py.

import { useEffect } from 'react'
import { apiFetch } from './api'

// Wait before reconnecting after the stream failed
const RETRY_MS = 5000

/**
 * Call onUpdate when the stream connects and whenever a trace changes.
 *
 * The stream is read with fetch, since EventSource cannot send the bearer
 * token. When it fails, onUpdate is called too: its own request then shows
 * the error, or logs out on an expired token.
 */
export function useUpdates(token: string, onUpdate: () => void) {
  useEffect(() => {
    const controller = new AbortController()
    let retry: ReturnType<typeof setTimeout> | undefined

    async function connect() {
      try {
        const res = await apiFetch('/updates', token, { signal: controller.signal })
        await readEvents(res, onUpdate)
        // The server closes the stream after a while: reconnect right away
        connect()
      } catch {
        if (controller.signal.aborted) return
        onUpdate()
        retry = setTimeout(connect, RETRY_MS)
      }
    }

    connect()
    return () => {
      controller.abort()
      clearTimeout(retry)
    }
  }, [token, onUpdate])
}

/** Call onEvent for each server-sent event, until the stream ends. */
async function readEvents(res: Response, onEvent: () => void) {
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    // Events end with a blank line
    let end
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const lines = buffer.slice(0, end).split('\n')
      buffer = buffer.slice(end + 2)
      // Lines starting with ':' are keep-alive pings
      if (lines.some((line) => line.startsWith('data:'))) onEvent()
    }
  }
}
