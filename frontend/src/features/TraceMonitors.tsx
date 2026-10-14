import { useCallback, useEffect, useState } from 'react'
import { ApiError, apiFetch, errorMessage } from '../api'
import { useSession } from './Auth'

/** Should mirror the TraceMonitor class in
 * src/governancekit/engine/trace_monitor.py
*/
type TraceMonitor = {
  // Trace monitors references some model.
  model_id: string

  // Has a field of instances?

  // Concurrent activities
  running: str
}


export function TraceMonitorList( ){
  const {token, logout} = useSession()
  const [traceMonitors, setTraceMonitors] = useState<TraceMonitorList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const



}
