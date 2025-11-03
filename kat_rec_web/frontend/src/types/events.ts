export type EventLevel = 'info' | 'warn' | 'error'

export interface EventEnvelope<T = any> {
  type: string // e.g. 't2r_scan_progress'
  version?: number
  ts?: string
  level?: EventLevel
  data?: T
}

// Known event tags (for IDE hints only; backend为权威)
export type T2REventType =
  | 't2r_scan_progress'
  | 't2r_fix_applied'
  | 't2r_runbook_stage_update'
  | 't2r_runbook_error'
  | 't2r_upload_progress'
  | 't2r_verify_result'
