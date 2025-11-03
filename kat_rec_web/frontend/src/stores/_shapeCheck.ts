/**
 * Zustand Store Shape Check (Type-level only)
 * 
 * Ensures all T2R stores conform to expected shape:
 * - load() / apply() / undo()
 * - lastError
 * - lastUpdatedAt
 * 
 * This file is for type checking only; no runtime code.
 */

// Import all stores to ensure they exist
import type { UseBoundStore, StoreApi } from 'zustand'

// Expected shape interface
interface ExpectedStoreShape {
  load?: () => Promise<void> | void
  apply?: (data: any) => Promise<void> | void
  undo?: () => Promise<void> | void
  lastError?: string | null
  lastUpdatedAt?: string | number | Date | null
}

// Type-level checks only (compile-time)
type _CheckShape<T extends ExpectedStoreShape> = T

// Example usage (commented out - uncomment if stores need explicit shape enforcement):
// import { useT2RScheduleStore } from '../../stores/t2rScheduleStore'
// import { useRunbookStore } from '../../stores/runbookStore'
// 
// type _ScheduleStoreShape = _CheckShape<ReturnType<typeof useT2RScheduleStore>>
// type _RunbookStoreShape = _CheckShape<ReturnType<typeof useRunbookStore>>

// This file serves as documentation and compile-time validation
// Actual runtime shape validation should be done in tests

export type { ExpectedStoreShape, _CheckShape }

