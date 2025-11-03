# Consolidation Plan

**Date**: 2025-01-XX  
**Branch**: `chore/consolidation-YYMMDD`  
**Goal**: Full repository consolidation - documentation debt, technical debt, cleanup/merge without reinventing wheels

## Execution Steps

### Phase 0: Branch & Guards ✅
- [x] Create working branch
- [x] Add consolidation plan document (this file)

### Phase 1: Documentation Debt
- [ ] Create `docs/DOCS_TOC.md` (auto-generated index)
- [ ] Create `docs/GLOSSARY.md` (MCRB/T2R naming convention)
- [ ] Create `docs/DEBT_REGISTER.md` (debt tracking)
- [ ] Scan and mark duplicate/stale docs
- [ ] Normalize doc filenames (kebab-case)
- [ ] Add markdownlint configuration
- [ ] Add `scripts/doc_lint.sh`

### Phase 2: Technical Debt
- [ ] Add `/api/mcrb/*` alias routes (preserve `/api/t2r/*`)
- [ ] Create `backend/t2r/ServiceRegistry.py` (centralize imports)
- [ ] Generate backend dependency graph
- [ ] Ensure atomic writes coverage
- [ ] Add WS buffer flush metrics
- [ ] Add state consistency layer

### Phase 3: Cleanup & Consolidation
- [ ] Update .gitignore/.dockerignore
- [ ] Frontend volume pruning (pnpm prune)
- [ ] Dead code scanning (backend + frontend)
- [ ] Build artifact separation
- [ ] Atomic write audit

### Phase 4: Verification & Metrics
- [ ] Create `scripts/verify_consolidation.sh`
- [ ] Update `scripts/verify_t2r.sh`
- [ ] Generate coverage reports
- [ ] Generate LOC summaries
- [ ] Calculate debt index

### Phase 5: Commit & Documentation
- [ ] Generate `docs/CONSOLIDATION_AUDIT.md`
- [ ] Commit all changes
- [ ] Output changeset summary

---

**Status**: In Progress  
**Last Updated**: 2025-01-XX

