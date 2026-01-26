# GridProgressIndicator Rendering Debug Analysis

## Dependency Map

### Data Flow Path

```
API Snapshot (t2rApi.ts)
  ↓
useScheduleHydrator (hooks/useScheduleHydrator.ts)
  ↓
Zustand Store (stores/scheduleStore.ts)
  ├─ eventsById: Record<string, ScheduleEvent>
  ├─ runbookSnapshots: Record<string, RunbookStageSnapshot>
  └─ visibleEventIds: string[] (computed selector)
  ↓
OverviewPage (app/(mcrb)/mcrb/overview/page.tsx)
  ├─ visibleEventIds (from store selector)
  └─ dateRange (from useScheduleWindow)
  ↓
OverviewGrid (components/mcrb/OverviewGrid.tsx)
  ├─ events (filtered from eventIds → eventsById)
  ├─ eventsByChannelAndDate (grouped by channel + date)
  └─ dateArray (filtered by workCursorDate)
  ↓
renderEventCell()
  ├─ primaryEvent (first event in cellEvents)
  ├─ isScaffold (no playlist + no prep ready + no render ready)
  ├─ isActive (channelState === 'in_production')
  ├─ shouldShowProgress (computed condition)
  └─ canUpload (render done && !publish done && !uploaded)
  ↓
GridProgressIndicatorV3 (components/mcrb/GridProgressIndicatorV3.tsx)
  ├─ eventId (from primaryEvent.id)
  └─ useEpisodePipelineStateV3(eventId)
      ├─ event (from store via createEventSelector)
      ├─ readiness (from store via createAssetStageReadinessSelector)
      └─ runbookState (from store.runbookSnapshots)
      ↓
      Returns: { assetStage, uploadState, verifyState }
  ↓
ProgressLineV3 / SkeletonLineV3 (rendered based on state)
```

### Key Conditions

#### shouldShowProgress (OverviewGrid.tsx:1447-1451)
```typescript
const shouldShowProgress = isScaffold || isActive || 
                           readiness.preparation.ready || 
                           readiness.render.ready || 
                           stages.render.done ||
                           !!(primaryEvent.assets.uploaded_at || primaryEvent.assets.uploaded)
```

**Evaluation Order:**
1. `isScaffold`: `!playlistPath && !preparation.ready && !render.ready`
2. `isActive`: `channelState[channelId] === 'in_production'`
3. `readiness.preparation.ready`: All prep assets ready
4. `readiness.render.ready`: Video + render flag ready
5. `stages.render.done`: Render stage complete
6. `actuallyUploaded`: Has uploaded_at or uploaded flag

#### GridProgressIndicatorV3 Rendering (GridProgressIndicatorV3.tsx:161-184)
```typescript
{finalAssetStage ? (
  <ProgressLineV3 assetStage={finalAssetStage} size={size} />
) : (
  <SkeletonLineV3 size={size} />
)}
```

**State Derivation:**
- `finalAssetStage`: `assetStageOverride ?? assetStage` (from hook)
- `finalUploadState`: `uploadStateOverride ?? uploadState` (from hook)
- `finalVerifyState`: `verifyStateOverride ?? verifyState` (from hook)

If hook returns `undefined`, shows `SkeletonLineV3`.

## Root Cause Analysis

### Issue 1: shouldShowProgress May Be False When It Should Be True

**Problem:**
- Events that are completed but not in `in_production` state won't show progress
- Events before work cursor are filtered out, but might still be in `visibleEventIds`
- `channelState` might not be set correctly for completed episodes

**Evidence:**
- Line 1444: `isActive = currentState === 'in_production'`
- If channel state is `'void'` but episode has progress, `shouldShowProgress` might still be true due to other conditions
- But if ALL conditions fail, progress won't show

### Issue 2: Event ID Mismatch

**Problem:**
- `eventIds` prop might contain IDs that don't exist in `eventsById`
- `primaryEvent.id` might not match `eventId` passed to `GridProgressIndicatorV3`
- Date filtering might remove events from `eventsByChannelAndDate` but they're still in `visibleEventIds`

**Evidence:**
- Line 257-261: `events = eventIds.map(id => eventsById[id]).filter(Boolean)`
- Line 431: Events filtered by `dateArraySet.has(event.date)`
- If event date is before work cursor, it's excluded from `eventsByChannelAndDate` but might still be in `eventIds`

### Issue 3: Hook Returns Undefined States

**Problem:**
- `useEpisodePipelineStateV3` might return `undefined` for `assetStage` when event exists
- This causes `SkeletonLineV3` to render instead of `ProgressLineV3`
- Hook logic might not handle edge cases correctly

**Evidence:**
- Line 251-258: If `!eventId || !event`, returns all `undefined`
- Line 260: `mapRunbookStageToAssetStage` might return `undefined` in some cases
- Line 123: Default is `'INIT'`, but if `readiness` is incomplete, might return `undefined`

### Issue 4: Store Hydration Race Condition

**Problem:**
- Store might be hydrated after component renders
- `eventsById` might be empty initially, then populated
- `runbookSnapshots` might not be synced with events

**Evidence:**
- `useScheduleHydrator` is async
- Store updates might not trigger re-renders if selectors don't change
- `visibleEventIds` selector might not update when events are added

## Proposed Fixes

### Fix 1: Add Comprehensive Debug Logging

Add debug logs to track:
- Event matching (eventId → eventsById)
- shouldShowProgress evaluation
- Hook state derivation
- Store hydration timing

### Fix 2: Fix shouldShowProgress Logic

Ensure progress shows for:
- All events with any progress (not just scaffold/active)
- Events that are completed but not published
- Events that are uploaded but not verified

### Fix 3: Fix Event Filtering

Ensure:
- `visibleEventIds` only contains events in `dateArray`
- Events are properly matched by date
- No events are lost during filtering

### Fix 4: Fix Hook State Derivation

Ensure:
- Hook always returns a valid state when event exists
- Default to `'INIT'` instead of `undefined`
- Handle edge cases in state mapping

### Fix 5: Add Memoization

Ensure:
- `eventsByChannelAndDate` properly memoized
- `shouldShowProgress` evaluation is stable
- No unnecessary re-renders

## Implementation Plan

1. Add debug logging to `renderEventCell`
2. Add debug logging to `GridProgressIndicatorV3`
3. Add debug logging to `useEpisodePipelineStateV3`
4. Fix `shouldShowProgress` condition
5. Fix event filtering logic
6. Fix hook state derivation
7. Add validation checks

