# Vibe Coding Master Prompt – Atlas Console Debugging Extension

## 概述

在浏览器侧提供一套统一的调试操作，用于观察状态流、组件生命周期、队列变化、事件广播和 UI 行为，使前端与后端的状态机保持同步，不产生 drift。

---

## 核心原则

1. **可重现性**: 所有调试动作必须可重现，不依赖临时手动 patch。
2. **真实状态验证**: 必须从控制台侧验证 state machine 的真实状态，而不是依赖预期逻辑。
3. **只读观测**: 控制台调试只用于观测，不允许篡改业务状态或触发无定义行为。
4. **文档化**: 每一次调试都记录成可复制的步骤，以便写入 DEVELOPMENT.md。

---

## 核心命令

### 1. expose_global_state

**目的**: 将核心 store 挂到 window 以便观测

**代码**:
```javascript
// 将核心 store 挂到 window 以便观测
window.KAT = {
  store: window.__ZUSTAND_STORE__ || window.__KAT_REC_STATE__,           
  bus: window.__EPISODE_FLOW_BUS__,
  socket: window.__T2R_WEBSOCKET__,
  // 如果store未暴露，尝试从React DevTools获取
  getStore: () => {
    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
      const hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
      // 尝试从React组件树中获取store
      return hook.renderers?.get(1)?.findFiberByHostInstance?.(document.body);
    }
    return null;
  }
};

console.log('✅ KAT调试对象已暴露');
console.log('   使用: KAT.store.getState() 检查状态');
```

**用法**: 允许直接在控制台调用 `KAT.store.getState()` 检查是否存在 state drift。

---

### 2. watch_socket_events

**目的**: 观测 upload/verify 阶段的 event 顺序

**代码**:
```javascript
if (!window.KAT) {
  console.error('❌ 请先运行 expose_global_state');
} else {
  const originalWS = window.WebSocket;
  let wsInstance = null;
  
  window.WebSocket = class extends originalWS {
    constructor(url, protocols) {
      super(url, protocols);
      if (url.includes('/ws/status')) {
        wsInstance = this;
        this.addEventListener('message', (event) => {
          try {
            const data = JSON.parse(event.data);
            const timestamp = new Date().toISOString();
            console.log(`[WS ${timestamp}]`, {
              type: data.type || data.event_type,
              episode_id: data.episode_id || data.event_id,
              state: data.state,
              payload: data
            });
          } catch (e) {
            console.log('[WS RAW]', event.data);
          }
        });
        console.log('✅ WebSocket监听已启动');
      }
    }
  };
  
  window.KAT.socket = wsInstance;
}
```

**用法**: 用于观测 upload/verify 阶段的 event 顺序，确保事件流不会乱序。

---

### 3. monitor_flow_bus

**目的**: 确认 EpisodeFlowBus 是否漏掉 _finish_command 或产生挂起

**代码**:
```javascript
if (!window.KAT) {
  console.error('❌ 请先运行 expose_global_state');
} else if (!window.KAT.bus) {
  console.warn('⚠️  EpisodeFlowBus 未暴露，尝试监听全局事件');
  
  // 监听自定义事件
  ['episode_flow_start', 'episode_flow_complete', 'episode_flow_error'].forEach(eventName => {
    window.addEventListener(eventName, (e) => {
      console.log(`[FLOW ${eventName}]`, e.detail);
    });
  });
  
  console.log('✅ 全局事件监听已启动');
} else {
  window.KAT.bus.subscribe((cmd) => {
    console.log('[FLOW]', {
      command: cmd.type || cmd.command,
      episode_id: cmd.episode_id,
      stage: cmd.stage,
      timestamp: new Date().toISOString()
    });
  });
  console.log('✅ EpisodeFlowBus 监听已启动');
}
```

**用法**: 确认 EpisodeFlowBus 是否漏掉 _finish_command 或产生挂起。

---

### 4. inspect_dom

**目的**: 观测 OverviewGrid / TaskPanel 在不同状态下的 DOM 行为

**代码**:
```javascript
function inspectDOM() {
  console.log('🔍 DOM 检查\n');
  
  // 1. 检查所有episode cells
  const cells = document.querySelectorAll('td[data-cell-id]');
  console.log(`📊 找到 ${cells.length} 个episode cells`);
  
  // 2. 检查GridProgressIndicator
  const indicators = document.querySelectorAll('[data-testid="grid-progress-indicator-v3"]');
  console.log(`📈 找到 ${indicators.length} 个GridProgressIndicator`);
  
  // 3. 检查上传图标
  const uploadIcons = document.querySelectorAll('svg[class*="lucide-upload"]');
  console.log(`📤 找到 ${uploadIcons.length} 个上传图标`);
  
  // 4. 检查motion元素
  const motionElements = document.querySelectorAll('[class*="motion"]');
  console.log(`🎬 找到 ${motionElements.length} 个motion元素`);
  
  // 5. 检查17日特定
  const cell17 = document.querySelector('td[data-cell-id*="2025-01-17"]');
  if (cell17) {
    console.log('\n✅ 17日cell详情:');
    console.log('   ID:', cell17.getAttribute('data-cell-id'));
    console.log('   有GridProgress:', !!cell17.querySelector('[data-testid="grid-progress-indicator-v3"]'));
    console.log('   有上传图标:', !!cell17.querySelector('svg[class*="lucide-upload"]'));
  }
  
  return { cells: cells.length, indicators: indicators.length, uploadIcons: uploadIcons.length };
}

inspectDOM();
```

**用法**: 观测 OverviewGrid / TaskPanel 在不同状态下的 DOM 行为，检查动画入口和出口。

---

### 5. performance_trace

**目的**: 判断 framer-motion 动画是否因为渲染过度或状态更新过频导致卡顿

**代码**:
```javascript
function performanceTrace(label = 'kat_debug') {
  const startMark = `${label}_start`;
  const endMark = `${label}_end`;
  const measureName = label;
  
  return {
    start: () => {
      performance.mark(startMark);
      console.log(`⏱️  性能追踪开始: ${label}`);
    },
    end: () => {
      performance.mark(endMark);
      performance.measure(measureName, startMark, endMark);
      const measure = performance.getEntriesByName(measureName)[0];
      console.log(`⏱️  性能追踪结果: ${label}`);
      console.log(`   耗时: ${measure.duration.toFixed(2)}ms`);
      
      // 检查是否超过阈值
      if (measure.duration > 100) {
        console.warn(`⚠️  耗时超过100ms，可能存在性能问题`);
      }
      
      return measure.duration;
    },
    measure: (fn) => {
      this.start();
      const result = fn();
      const duration = this.end();
      return { result, duration };
    }
  };
}

// 使用示例
const trace = performanceTrace('grid_render');
trace.start();
// ... 执行操作 ...
trace.end();
```

**用法**: 判断 framer-motion 动画是否因为渲染过度或状态更新过频导致卡顿。

---

## 工作流程

### 标准调试流程

1. **启动本地开发环境后，按 Option+Command+I 打开控制台**

2. **运行 expose_global_state 以确保所有关键全局对象可访问**

3. **在切换 EpisodeFlow 阶段或点选 OverviewGrid 时，运行 watch_socket_events 和 monitor_flow_bus**，观察事件是否与预期一致

4. **如果存在 UI 不更新或卡顿，通过 inspect_dom 和 performance_trace 诊断** DOM 数量、动画成本、渲染层级变化

5. **所有异常必须写入 DEVELOPMENT.md 的 "Atlas Debug Session" 区段**，并附带复现步骤和控制台日志

---

## 故障模式处理

### 1. 事件顺序乱序

**症状**: WebSocket 事件推送顺序与预期不符

**调试步骤**:
```javascript
// 记录所有WebSocket消息
const wsMessages = [];
watch_socket_events();
// 执行操作...
console.log('WebSocket消息序列:', wsMessages);
```

**记录内容**:
- WebSocket 推送的原始 payload
- 事件时间戳
- 后端事件调度日志

---

### 2. State Drift

**症状**: Zustand store 状态与 ASR snapshot 不一致

**调试步骤**:
```javascript
// 检查store状态
const storeState = KAT.store.getState();
const events = Object.values(storeState.eventsById || {});

// 检查特定episode
const episode17 = events.find(e => e.date === '2025-01-17');
console.log('Store中的17日节目:', episode17);

// 检查ASR snapshot（如果可访问）
if (window.__ASR_SNAPSHOT__) {
  const asrSnapshot = window.__ASR_SNAPSHOT__;
  console.log('ASR Snapshot:', asrSnapshot);
  
  // 对比差异
  const diff = compareState(episode17, asrSnapshot);
  console.log('状态差异:', diff);
}
```

**记录内容**:
- `KAT.store.getState()` 的完整输出
- ASR snapshot 的完整输出
- 差异对比结果
- 确认是否为 Zustand 订阅未触发或 React 组件未重渲染

---

### 3. UI 卡顿

**症状**: 页面响应缓慢，动画不流畅

**调试步骤**:
```javascript
// 性能追踪
const trace = performanceTrace('ui_update');
trace.start();

// 触发UI更新
// ... 操作 ...

trace.end();

// 检查DOM数量
inspect_dom();

// 检查motion元素
const motionElements = document.querySelectorAll('[class*="motion"]');
console.log('Motion元素数量:', motionElements.length);
motionElements.forEach((el, i) => {
  const style = window.getComputedStyle(el);
  console.log(`Motion ${i}:`, {
    transform: style.transform,
    opacity: style.opacity,
    willChange: style.willChange
  });
});
```

**记录内容**:
- 具体的渲染时间（通过 performance_trace）
- DOM 节点数量
- Motion 元素数量
- 确认是否与 framer-motion 或过多 DOM 节点有关

---

## 交付物

### Debug Summary 模板

```markdown
## Atlas Debug Session - [日期] - [问题描述]

### 问题
[简要描述问题]

### 调试步骤
1. [步骤1]
2. [步骤2]
3. [步骤3]

### 控制台输出
\`\`\`
[复制控制台输出]
\`\`\`

### 发现
- [发现1]
- [发现2]

### 修复建议
- [建议1]
- [建议2]

### 复现步骤
1. [步骤1]
2. [步骤2]
```

---

## 响应模式

任何与 Atlas 控制台相关的问题一律走 **ATLAS_DEBUGGING** 模块，从中选择合适的逻辑检查、性能测试、事件观测或 DOM 分析方法。

---

## 集成到 Vibe Coding Master Prompt

将以下内容添加到 **MASTER PROMPT → AUTOMATION 或 DEVELOPMENT → DEBUGGING** 部分：

```
ATLAS_DEBUGGING:

  GOAL: 在浏览器侧提供一套统一的调试操作，用于观察状态流、组件生命周期、队列变化、事件广播和 UI 行为，使前端与后端的状态机保持同步，不产生 drift。

  PRINCIPLES:
    1. 所有调试动作必须可重现，不依赖临时手动 patch。
    2. 必须从控制台侧验证 state machine 的真实状态，而不是依赖预期逻辑。
    3. 控制台调试只用于观测，不允许篡改业务状态或触发无定义行为。
    4. 每一次调试都记录成可复制的步骤，以便写入 DEVELOPMENT.md。

  CORE_COMMANDS:
    - expose_global_state: 将核心 store 挂到 window 以便观测
    - watch_socket_events: 观测 upload/verify 阶段的 event 顺序
    - monitor_flow_bus: 确认 EpisodeFlowBus 是否漏掉 _finish_command
    - inspect_dom: 观测 OverviewGrid / TaskPanel 在不同状态下的 DOM 行为
    - performance_trace: 判断 framer-motion 动画是否导致卡顿

  WORKFLOW:
    1. 启动本地开发环境后，按 Option+Command+I 打开控制台。
    2. 运行 expose_global_state 以确保所有关键全局对象可访问。
    3. 在切换 EpisodeFlow 阶段或点选 OverviewGrid 时，运行 watch_socket_events 和 monitor_flow_bus。
    4. 如果存在 UI 不更新或卡顿，通过 inspect_dom 和 performance_trace 诊断。
    5. 所有异常必须写入 DEVELOPMENT.md 的 "Atlas Debug Session" 区段。

  FAILURE_MODES:
    1. 事件顺序乱序 → 记录 WebSocket 推送的原始 payload
    2. State drift → 记录 KAT.store.getState() 和 ASR snapshot 的差异
    3. UI 卡顿 → 通过 performance_trace 提供具体的渲染时间

  RESPONSE_MODE:
    任何与 Atlas 控制台相关的问题一律走 ATLAS_DEBUGGING 模块。
```

---

**版本**: 1.0  
**创建日期**: 2025-01-XX  
**维护者**: Vibe Coding Infra Team

