# Atlas 浏览器控制台调试指南

## 快速打开控制台

### macOS
- `⌥ + ⌘ + I` (Option + Command + I) - 打开开发者工具
- `⌥ + ⌘ + J` (Option + Command + J) - 直接打开控制台
- `⌥ + ⌘ + C` (Option + Command + C) - 打开元素选择器

### Windows/Linux
- `Ctrl + Shift + I` - 打开开发者工具
- `Ctrl + Shift + J` - 直接打开控制台

---

## Kat Rec 项目专用调试代码

### 1. 检查17日节目数据

```javascript
// 在控制台执行此代码块
(async () => {
  console.log('🔍 检查17日节目数据...\n');
  
  // 方法1: 通过DOM查找
  const cell17 = document.querySelector('td[data-cell-id*="2025-01-17"]');
  if (cell17) {
    console.log('✅ 找到17日cell DOM元素:', cell17);
    console.log('   Cell ID:', cell17.getAttribute('data-cell-id'));
  } else {
    console.log('❌ 未找到17日cell DOM元素');
  }
  
  // 方法2: 检查GridProgressIndicator
  const progressIndicators = document.querySelectorAll('[data-testid="grid-progress-indicator-v3"]');
  console.log(`\n📊 找到 ${progressIndicators.length} 个进度指示器`);
  
  // 方法3: 检查上传图标
  const uploadIcons = document.querySelectorAll('svg[class*="lucide-upload"], [class*="Upload"]');
  console.log(`📤 找到 ${uploadIcons.length} 个上传相关元素`);
  
  // 方法4: 检查React组件（如果React DevTools可用）
  if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
    console.log('✅ React DevTools 已加载');
  } else {
    console.log('ℹ️  React DevTools 未检测到（可能需要安装扩展）');
  }
})();
```

### 2. 检查Zustand Store状态

```javascript
// 检查store是否暴露
if (window.__ZUSTAND_STORE__) {
  const store = window.__ZUSTAND_STORE__;
  const state = store.getState();
  
  console.log('📦 Zustand Store 状态:');
  console.log('  - Events数量:', Object.keys(state.eventsById || {}).length);
  console.log('  - Channel State:', state.channelState);
  
  // 查找17日节目
  const events = Object.values(state.eventsById || {});
  const event17 = events.find(e => 
    e.date === '2025-01-17' || 
    e.id === '20250117' || 
    e.id?.includes('20250117')
  );
  
  if (event17) {
    console.log('\n✅ 找到17日节目:', {
      id: event17.id,
      date: event17.date,
      playlistPath: event17.playlistPath,
      hasOutputFolder: event17.hasOutputFolder,
      assets: event17.assets,
      uploadState: event17.uploadState
    });
  } else {
    console.log('\n❌ 未在store中找到17日节目');
    console.log('   所有日期:', [...new Set(events.map(e => e.date))].sort());
  }
} else {
  console.log('⚠️  Zustand Store 未暴露到 window');
  console.log('   提示: 可以在 scheduleStore.ts 中添加: window.__ZUSTAND_STORE__ = useScheduleStore');
}
```

### 3. 实时监听WebSocket事件

```javascript
// 监听所有WebSocket消息
const originalWebSocket = window.WebSocket;
window.WebSocket = class extends originalWebSocket {
  constructor(url, protocols) {
    super(url, protocols);
    this.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.episode_id?.includes('20250117') || data.event_id?.includes('20250117')) {
          console.log('📡 17日节目WebSocket消息:', data);
        }
      } catch (e) {
        // 非JSON消息，忽略
      }
    });
  }
};

console.log('✅ WebSocket监听已启动（仅显示17日相关消息）');
```

### 4. 检查GridProgressIndicatorV3渲染

```javascript
// 检查17日cell中的GridProgressIndicator
const cell17 = document.querySelector('td[data-cell-id*="2025-01-17"]');
if (cell17) {
  const progressIndicator = cell17.querySelector('[data-testid="grid-progress-indicator-v3"]');
  if (progressIndicator) {
    console.log('✅ GridProgressIndicatorV3 已渲染');
    console.log('   元素:', progressIndicator);
    console.log('   视图模式:', progressIndicator.getAttribute('data-view'));
    
    // 检查三个进度条
    const lines = progressIndicator.querySelectorAll('div[class*="rounded-full"]');
    console.log(`   找到 ${lines.length} 个进度条`);
  } else {
    console.log('❌ GridProgressIndicatorV3 未渲染');
    console.log('   检查条件: shouldShowProgress 可能为 false');
  }
  
  // 检查上传图标
  const uploadIcon = cell17.querySelector('svg[class*="lucide-upload"]');
  if (uploadIcon) {
    console.log('✅ 上传图标已显示');
  } else {
    console.log('❌ 上传图标未显示');
    console.log('   检查条件: canUpload 可能为 false 或不在显示范围内');
  }
} else {
  console.log('❌ 未找到17日cell');
}
```

### 5. 强制显示GridProgressIndicator（调试用）

```javascript
// 临时强制显示（仅用于调试，刷新后失效）
const cell17 = document.querySelector('td[data-cell-id*="2025-01-17"]');
if (cell17) {
  // 检查是否已有进度指示器
  let indicator = cell17.querySelector('[data-testid="grid-progress-indicator-v3"]');
  
  if (!indicator) {
    console.log('🔧 强制创建GridProgressIndicatorV3（调试用）...');
    
    // 创建容器
    const container = document.createElement('div');
    container.className = 'w-full flex-1 flex items-center justify-center px-2';
    container.style.minHeight = '24px';
    container.setAttribute('data-testid', 'grid-progress-indicator-v3-debug');
    
    // 创建三个进度条（模拟）
    for (let i = 0; i < 3; i++) {
      const line = document.createElement('div');
      line.className = 'w-full h-1 rounded-full bg-slate-400/30 mb-0.5';
      container.appendChild(line);
    }
    
    // 插入到cell中
    const contentArea = cell17.querySelector('.flex.flex-col.items-center.justify-center');
    if (contentArea) {
      contentArea.appendChild(container);
      console.log('✅ 已创建调试用进度指示器');
    }
  } else {
    console.log('✅ 进度指示器已存在');
  }
}
```

### 6. 检查shouldShowProgress条件

```javascript
// 模拟检查显示条件
const cell17 = document.querySelector('td[data-cell-id*="2025-01-17"]');
if (cell17) {
  console.log('🔍 检查显示条件...\n');
  
  // 检查cell的class
  const cellClasses = cell17.className;
  console.log('Cell classes:', cellClasses);
  console.log('  - isScaffold样式:', cellClasses.includes('bg-[rgba(16,185,129,0.08)]'));
  console.log('  - isActive样式:', cellClasses.includes('bg-dark-bg-primary'));
  
  // 检查是否有进度指示器容器
  const progressContainer = cell17.querySelector('.w-full.flex-1.flex.items-center.justify-center');
  if (progressContainer) {
    console.log('✅ 找到进度指示器容器');
    const hasIndicator = progressContainer.querySelector('[data-testid="grid-progress-indicator-v3"]');
    console.log('  - 包含GridProgressIndicatorV3:', !!hasIndicator);
  } else {
    console.log('❌ 未找到进度指示器容器');
  }
}
```

### 7. 监听React组件更新

```javascript
// 如果React DevTools可用，监听组件更新
if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
  const hook = window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
  
  // 监听组件渲染
  const originalOnCommitFiberRoot = hook.onCommitFiberRoot;
  hook.onCommitFiberRoot = function(id, root, ...args) {
    if (originalOnCommitFiberRoot) {
      originalOnCommitFiberRoot.call(this, id, root, ...args);
    }
    
    // 检查是否有17日相关的更新
    const fiber = root.current;
    if (fiber && fiber.memoizedProps) {
      const props = fiber.memoizedProps;
      if (props.eventId?.includes('20250117') || props.date?.includes('2025-01-17')) {
        console.log('🔄 17日节目组件更新:', props);
      }
    }
  };
  
  console.log('✅ React更新监听已启动');
} else {
  console.log('ℹ️  React DevTools未检测到');
}
```

### 8. 检查网络请求

```javascript
// 在Network面板中查看，或使用Performance Observer
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.name.includes('/api/t2r/episodes') || entry.name.includes('20250117')) {
      console.log('🌐 相关网络请求:', {
        name: entry.name,
        duration: entry.duration,
        size: entry.transferSize
      });
    }
  }
});

observer.observe({ entryTypes: ['resource'] });
console.log('✅ 网络请求监听已启动');
```

---

## 常用调试命令速查

### 快速检查17日节目

```javascript
// 一键检查（复制粘贴到控制台）
(() => {
  const cell = document.querySelector('td[data-cell-id*="2025-01-17"]');
  const indicator = cell?.querySelector('[data-testid="grid-progress-indicator-v3"]');
  const uploadIcon = cell?.querySelector('svg[class*="lucide-upload"]');
  
  console.log({
    'Cell存在': !!cell,
    'GridProgress显示': !!indicator,
    '上传图标显示': !!uploadIcon,
    'Cell ID': cell?.getAttribute('data-cell-id'),
    'Cell Classes': cell?.className
  });
})();
```

### 检查所有日期

```javascript
// 列出所有显示的日期
const cells = document.querySelectorAll('td[data-cell-id]');
const dates = Array.from(cells).map(cell => {
  const id = cell.getAttribute('data-cell-id');
  const date = id?.split('-').slice(1).join('-');
  const hasProgress = !!cell.querySelector('[data-testid="grid-progress-indicator-v3"]');
  return { date, hasProgress };
});

console.table(dates.filter(d => d.date));
```

### 强制刷新数据

```javascript
// 触发数据刷新
if (window.location) {
  window.location.reload();
} else {
  console.log('无法刷新，请手动刷新页面');
}
```

---

## 调试17日节目显示问题的完整流程

### 步骤1: 打开控制台
按 `⌥ + ⌘ + I` 打开开发者工具

### 步骤2: 执行快速检查
```javascript
// 复制粘贴到控制台
(() => {
  console.log('🔍 17日节目调试检查\n');
  
  // 1. DOM检查
  const cell = document.querySelector('td[data-cell-id*="2025-01-17"]');
  console.log('1. Cell DOM:', cell ? '✅ 存在' : '❌ 不存在');
  
  // 2. 进度指示器检查
  const indicator = cell?.querySelector('[data-testid="grid-progress-indicator-v3"]');
  console.log('2. GridProgressIndicator:', indicator ? '✅ 显示' : '❌ 未显示');
  
  // 3. 上传图标检查
  const uploadIcon = cell?.querySelector('svg[class*="lucide-upload"]');
  console.log('3. 上传图标:', uploadIcon ? '✅ 显示' : '❌ 未显示');
  
  // 4. 检查条件
  if (cell) {
    const classes = cell.className;
    console.log('4. Cell状态:');
    console.log('   - isScaffold:', classes.includes('bg-[rgba(16,185,129,0.08)]'));
    console.log('   - isActive:', classes.includes('bg-dark-bg-primary'));
  }
  
  // 5. 检查store（如果可用）
  if (window.__ZUSTAND_STORE__) {
    const state = window.__ZUSTAND_STORE__.getState();
    const event17 = Object.values(state.eventsById || {}).find(e => 
      e.date === '2025-01-17' || e.id?.includes('20250117')
    );
    console.log('5. Store中的17日节目:', event17 ? '✅ 存在' : '❌ 不存在');
    if (event17) {
      console.log('   详情:', {
        id: event17.id,
        date: event17.date,
        playlistPath: event17.playlistPath,
        uploaded: event17.assets?.uploaded_at || event17.assets?.uploaded
      });
    }
  }
})();
```

### 步骤3: 根据结果判断

**如果Cell不存在**:
- 检查日期范围是否包含17日
- 检查work cursor是否过滤了17日
- 检查API是否返回了17日数据

**如果Cell存在但GridProgress未显示**:
- 检查 `shouldShowProgress` 条件
- 检查事件数据是否完整
- 检查React组件是否正常渲染

**如果上传图标未显示**:
- 检查 `canUpload` 条件
- 检查渲染是否完成
- 检查上传状态

---

## 性能调试

### 检查动画性能

```javascript
// 在Performance面板中记录，然后执行
performance.mark('grid-progress-start');

// 操作页面...

performance.mark('grid-progress-end');
performance.measure('grid-progress', 'grid-progress-start', 'grid-progress-end');

const measure = performance.getEntriesByName('grid-progress')[0];
console.log('动画耗时:', measure.duration, 'ms');
```

### 检查Framer Motion动画

```javascript
// 检查motion组件
const motionDivs = document.querySelectorAll('[class*="motion"]');
console.log('Motion元素数量:', motionDivs.length);

// 检查动画状态
motionDivs.forEach((el, i) => {
  const style = window.getComputedStyle(el);
  console.log(`Motion ${i}:`, {
    transform: style.transform,
    opacity: style.opacity,
    willChange: style.willChange
  });
});
```

---

## 故障排除

### 如果控制台无法打开

1. **检查Atlas设置**:
   - 查看是否有"禁用开发者工具"选项
   - 尝试使用菜单栏: View → Developer → Developer Tools

2. **使用Chrome作为替代**:
   ```bash
   open -a "Google Chrome" "http://localhost:3000/mcrb/overview"
   ```

3. **使用Chrome工程模式（自动打开DevTools）**:
   ```bash
   open -na "Google Chrome" \
     --args --auto-open-devtools-for-tabs \
     "http://localhost:3000/mcrb/overview"
   ```

### 如果React DevTools不可用

安装React Developer Tools扩展：
1. 打开Chrome Web Store
2. 搜索"React Developer Tools"
3. 安装扩展
4. 重启Atlas

---

## 调试输出示例

执行调试代码后，你应该看到类似这样的输出：

```
🔍 17日节目调试检查

1. Cell DOM: ✅ 存在
2. GridProgressIndicator: ✅ 显示
3. 上传图标: ✅ 显示
4. Cell状态:
   - isScaffold: false
   - isActive: true
5. Store中的17日节目: ✅ 存在
   详情: {
     id: "20250117",
     date: "2025-01-17",
     playlistPath: "/path/to/playlist.json",
     uploaded: false
   }
```

---

**最后更新**: 2025-01-XX  
**适用版本**: Atlas (ChatGPT Browser)  
**项目**: Kat Rec Web Frontend

