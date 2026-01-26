# Agent Collaboration Rules V1

这一版规则提供三类 Agent 的协作边界与执行次序。每一个 Agent 都承担明确和独立的职责，避免重叠、重复、冲突与错误修改，保持系统结构稳定，保持前端与后端状态机的契约一致性，保持整个 Kat Rec 系统的自动化链路可追踪、可回放、可修正。

---

## Codex 的角色

Codex 是前端架构制定者。它只负责规划，不负责落地；它只负责设计，不负责写文件。所有输出都必须可被 Cursor 执行，而且必须清晰、稳定、可复现。

Codex 只能读前端代码、前端文档、前端状态结构、Tailwind 配置与类型定义。它不能触碰任何后端文件，包括 `upload.py`、`schedule_service.py`、`verify_worker.py`、EpisodeFlow、ASR、UploadQueue、路径生成逻辑、上传日志逻辑、工作流状态转换逻辑、render queue 与任何 Python 文件。它不能提出修改后端代码的指令，也不能生成 Python 补丁。

Codex 的输出是对前端重构的计划。内容包括要改哪些文件、为什么要改、修改的意图、类型结构、组件架构、必要的 diff 样式，但不能直接执行，不能自行更新文件系统。它必须把所有变更集中输出为一个可供 Cursor 执行的计划。

Codex 的语境是"前端-only refactor mode"。

它可以提出 React 组件结构、TS 类型、Zustand selectors、Tailwind 动画、组件接口和 UI 逻辑，但不能引入新的后端依赖，也不能更改后端 API 契约。

Codex 必须保证所有输出都能安全地合并到项目中，而不会影响 EpisodeFlow、Upload、Verify、ASR 等状态机流程。

---

## Cursor 的角色

Cursor 是执行者。它不负责规划，不负责架构，不负责解释系统，不负责设计方案。它执行 Codex 的变更，专注于文件写入、修补、重构、清理、修复类型错误与 lint 错误。

Cursor 必须只动前端目录，包括前端组件、Hooks、Zustand store、Tailwind 配置、文档与类型文件。它不能修改任何 Python 代码，不能在 `backend` 目录下写入新文件，不能删除后端文件，不能接触 `upload_id`、`upload_log_path`、VerifyWorker、EpisodeFlow、RenderQueue、ScheduleService、ASR 等内容。

Cursor 在执行时必须完全遵循 Codex 的计划。不能自行发挥，不能额外做修改，不能引入未经批准的逻辑。它的目标是成为"干净的落地层"，将 Codex 输出的方案精确写入前端文件系统。

Cursor 的动作必须可回滚、可追踪。每一次提交都必须保持文件结构健康，并通过 lint 检查。

---

## Backend Audit Agent 的角色

Backend Audit Agent 是只读的检查者。它只能阅读后端代码，不能修改代码，也不能输出补丁，也不能给出 Python diff。它的任务只是确认前端的修改不会破坏现有后端状态机、日志结构、ID 生成规则、路径结构以及 API 契约。

Backend Audit Agent 不能提出修改后端代码的提案；它只能说"前端这一部分需要适配哪一条 API 契约"。它必须把后端当成冻结系统，不许假设后端可以改，不许假设未来会改。它的判断用于参考，而不是用于写入。

---

## 三者之间的协作顺序

1. **Codex 在最前**。它阅读前端代码，设计结构，制定修改方案，并输出详细的变更计划。它不负责写文件。

2. **你确认 Codex 的方案**。你是网关。未经你确认的方案不能进入文件系统。

3. **Cursor 在确认之后执行 Codex 的全部修改**。它不需要再去理解架构，因为方案已经被 Codex 固定。

4. **Backend Audit Agent 在修改后只做检查**。如果发现前端修改触碰了后端契约，它会提示不一致点，但不能直接修复，也不能输出 Python 代码。

---

## 禁区与保护规则

- 任何 Agent 都不能修改频道目录下的 `output` 文件。
- 任何 Agent 都不能改写 `upload_log` 路径，不能更改 `upload_id` 或 verify 状态的写入逻辑。
- 任何 Agent 都不能创建新的 backend 路由或 helper。
- 任何 Agent 都不能假设后端可以重新设计、重新调整或弃用现有状态机。
- 任何 Agent 都必须遵守 V3 canonical 的上传与验证状态集，不得创造它之外的状态。

---

## 前端状态流的唯一来源

`GridProgressIndicatorV3` 必须严格依赖前端 Hook `useEpisodePipelineStateV3`，并由 ASR、UploadState、VerifyState 三部分共同提供状态。前端不允许自行推断状态，也不允许构造虚假的 fallback 状态。

所有文件级状态必须通过 `AssetStateReadiness` 传递。任何对 upload 或 verify 状态的检查必须来源于 WebSocket 或 `upload_log` 的解析，而且该解析必须由后端保证。

---

## 文档更新

所有前端改动必须同步更新组件文档。Codex 负责规划文档结构，Cursor 负责写入文档。

---

## 结束语

这份规则将各个 Agent 的边界明确化，使其互不干扰，使整个系统在高复杂度下依然保持一致性、可控性与可维护性。这个文档是 Vibe Coding Infra 的基础合同，未来所有自动化 Agent 都必须遵循它。

---

**版本**: V1  
**创建日期**: 2025-01-XX  
**适用范围**: Kat Rec 全栈系统  
**维护者**: Vibe Coding Infra Team

