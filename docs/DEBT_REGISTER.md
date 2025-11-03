# Technical & Documentation Debt Register

**Last Updated**: 2025-01-XX  
**Purpose**: Track technical debt, documentation debt, and build issues for prioritization

## Debt Index Formula

```
DI = (DuplicationRatio × Coupling × Complexity) / max(0.3, Coverage)
```

**Where**:
- DuplicationRatio: Lines duplicated / Total lines (0-1)
- Coupling: Average cross-module dependencies (1-5 scale)
- Complexity: Cyclomatic complexity average (1-5 scale)
- Coverage: Test coverage ratio (0-1)

**Buckets**:
- S (Small): DI < 2.0
- M (Medium): 2.0 ≤ DI < 5.0
- L (Large): DI ≥ 5.0

## Current Debt Index

**Baseline**: TBD (will be calculated after consolidation scripts run)

## Debt Items

| Type | Item | Impact | Effort | Owner | Sprint | Status | Notes |
|------|------|--------|--------|-------|--------|--------|-------|
| docs | Duplicate sprint docs | 2 | S | - | Backlog | tracked | Multiple sprint2/sprint3 variants |
| docs | Missing API documentation | 3 | M | - | Backlog | tracked | Need OpenAPI spec docs |
| tech | Atomic write coverage | 4 | M | - | Current | in-progress | Some JSON writes not atomic |
| tech | WS buffer flush metrics | 3 | S | - | Current | in-progress | Need /metrics/ws-health endpoint |
| tech | State consistency layer | 4 | M | - | Backlog | planned | Frontend state → backend mapping |
| build | Frontend bundle size | 2 | S | - | Backlog | tracked | node_modules optimization |
| build | Dead code in backend | 2 | S | - | Backlog | tracked | vulture scan pending |
| build | Dead code in frontend | 2 | S | - | Backlog | tracked | ts-prune scan pending |

## Resolution Tracking

### Resolved
- ✅ Route alias /api/mcrb/* added (dual prefix support)
- ✅ Documentation TOC auto-generated

### In Progress
- 🔄 Atomic write audit and patching
- 🔄 WS metrics endpoint (/metrics/ws-health)
- 🔄 Dead code scanning

### Planned
- 📋 State consistency layer implementation
- 📋 Dependency graph generation
- 📋 Frontend bundle optimization

---

**Update Process**: This register is updated during consolidation cycles. Each item should include impact (1-5), effort estimate (S/M/L), and resolution status.

