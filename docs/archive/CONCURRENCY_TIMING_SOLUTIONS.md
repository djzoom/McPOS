# 时序/并发问题系统性解决方案

## 问题分类

### 1. Schedule 更新的竞态条件（Read-Modify-Write）

**问题**：
- 多个请求同时读取 schedule
- 各自修改后保存
- 后保存的会覆盖先保存的修改

**影响范围**：
- `plan.py`: 更新 timeline_csv, audio_path
- `automation.py`: 更新 description, title, cover 等
- `episodes.py`: 创建/更新 episode
- 所有直接调用 `load_schedule_master` + `save_schedule_master` 的地方

**解决方案**：
1. 使用文件锁（`fcntl` 或 `asyncio.Lock`）
2. 使用乐观锁（版本号/时间戳）
3. 使用事务性更新（临时文件+原子重命名，已有）

### 2. 文件写入和验证的时序问题

**问题**：
- 文件写入后立即检查存在性可能失败
- 文件写入后立即读取可能失败
- 文件系统延迟导致验证失败

**影响范围**：
- Timeline CSV 生成
- 所有文件写入操作
- 文件存在性检查

**解决方案**：
1. 写入后强制同步（`fsync`）
2. 等待文件系统同步（`time.sleep`）
3. 重试机制（指数退避）
4. 使用文件系统事件监听（`watchdog`）

### 3. 锁的超时和死锁问题

**问题**：
- 某些锁没有超时机制
- 死锁导致系统阻塞
- 锁的粒度不合适

**影响范围**：
- `_queue_lock` (plan.py) - ✅ 已有超时
- `_LOCK` (render_queue.py) - ✅ 已有超时
- `_STATE_LOCK` (channel_automation.py) - ❌ 无超时
- Schedule 文件锁 - ❌ 无锁

**解决方案**：
1. 为所有锁添加超时机制
2. 使用上下文管理器确保锁释放
3. 添加死锁检测和恢复机制

### 4. 文件操作的原子性问题

**问题**：
- 多个进程同时写入同一文件
- 文件写入不完整就被读取
- 文件删除和检查之间的竞态条件

**影响范围**：
- 所有文件写入操作
- 文件存在性检查
- 文件删除操作

**解决方案**：
1. 使用临时文件+原子重命名（已有）
2. 使用文件锁（`fcntl.flock`）
3. 使用文件版本号/时间戳

## 实施方案

### 阶段 1: Schedule 更新的并发控制

#### 1.1 创建 Schedule 更新锁

```python
# kat_rec_web/backend/t2r/services/schedule_service.py

import asyncio
from typing import Dict

# 每个 channel 一个锁，避免跨 channel 阻塞
_schedule_locks: Dict[str, asyncio.Lock] = {}
_schedule_lock_timeout = 5.0

async def _acquire_schedule_lock(channel_id: str, timeout: float = _schedule_lock_timeout) -> None:
    """获取 schedule 更新锁"""
    if channel_id not in _schedule_locks:
        _schedule_locks[channel_id] = asyncio.Lock()
    
    try:
        await asyncio.wait_for(_schedule_locks[channel_id].acquire(), timeout=timeout)
    except asyncio.TimeoutError:
        raise RuntimeError(f"Failed to acquire schedule lock for {channel_id} after {timeout}s")

def _release_schedule_lock(channel_id: str) -> None:
    """释放 schedule 更新锁"""
    if channel_id in _schedule_locks:
        if _schedule_locks[channel_id].locked():
            _schedule_locks[channel_id].release()
```

#### 1.2 创建事务性 Schedule 更新函数

```python
async def async_update_schedule_atomic(
    channel_id: str,
    update_func: callable,
    *args,
    **kwargs
) -> bool:
    """
    原子性更新 schedule，使用锁防止并发冲突。
    
    Args:
        channel_id: Channel ID
        update_func: 更新函数，接收 (schedule_dict, *args, **kwargs)，返回更新后的 schedule
        *args, **kwargs: 传递给 update_func 的参数
    
    Returns:
        True if successful, False otherwise
    """
    await _acquire_schedule_lock(channel_id)
    try:
        # 读取最新 schedule
        schedule = await async_load_schedule_master(channel_id)
        if not schedule:
            logger.error(f"Failed to load schedule for {channel_id}")
            return False
        
        # 应用更新
        updated_schedule = update_func(schedule, *args, **kwargs)
        
        # 保存
        return await async_save_schedule_master(updated_schedule, channel_id)
    finally:
        _release_schedule_lock(channel_id)
```

### 阶段 2: 文件写入的可靠性增强

#### 2.1 创建可靠的文件写入函数

```python
# kat_rec_web/backend/t2r/utils/reliable_file_ops.py

import asyncio
from pathlib import Path
from typing import Optional
import time

async def reliable_write_text(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    max_retries: int = 3,
    verify_after_write: bool = True,
    sync_delay: float = 0.1
) -> bool:
    """
    可靠地写入文本文件，包含验证和重试机制。
    
    Args:
        file_path: 目标文件路径
        content: 要写入的内容
        encoding: 编码
        max_retries: 最大重试次数
        verify_after_write: 写入后是否验证
        sync_delay: 文件系统同步延迟（秒）
    
    Returns:
        True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            file_path.write_text(content, encoding=encoding)
            
            # 强制同步
            with file_path.open("r+b") as f:
                f.flush()
                os.fsync(f.fileno())
            
            # 等待文件系统同步
            await asyncio.sleep(sync_delay)
            
            # 验证文件
            if verify_after_write:
                if not file_path.exists():
                    raise FileNotFoundError(f"File does not exist after write: {file_path}")
                
                # 验证内容
                read_content = file_path.read_text(encoding=encoding)
                if read_content != content:
                    raise ValueError(f"File content mismatch after write: {file_path}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"File write failed (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                await asyncio.sleep(0.1 * (2 ** attempt))  # 指数退避
            else:
                logger.error(f"File write failed after {max_retries} attempts: {e}")
                return False
    
    return False
```

### 阶段 3: 统一锁的超时机制

#### 3.1 创建锁管理器

```python
# kat_rec_web/backend/t2r/utils/lock_manager.py

import asyncio
from typing import Dict, Optional
from contextlib import asynccontextmanager

class LockManager:
    """统一的锁管理器，提供超时和死锁检测"""
    
    def __init__(self, default_timeout: float = 5.0):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._default_timeout = default_timeout
        self._lock_holders: Dict[str, str] = {}  # lock_name -> holder_info
    
    @asynccontextmanager
    async def acquire(self, lock_name: str, timeout: Optional[float] = None, holder_info: str = ""):
        """获取锁，带超时和自动释放"""
        timeout = timeout or self._default_timeout
        
        if lock_name not in self._locks:
            self._locks[lock_name] = asyncio.Lock()
        
        try:
            await asyncio.wait_for(self._locks[lock_name].acquire(), timeout=timeout)
            self._lock_holders[lock_name] = holder_info
            yield
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to acquire lock '{lock_name}' after {timeout}s (holder: {self._lock_holders.get(lock_name, 'unknown')})")
        finally:
            if lock_name in self._locks and self._locks[lock_name].locked():
                self._locks[lock_name].release()
                self._lock_holders.pop(lock_name, None)

# 全局锁管理器
_lock_manager = LockManager(default_timeout=5.0)
```

### 阶段 4: 文件操作的原子性保证

#### 4.1 增强原子写入函数

```python
# kat_rec_web/backend/t2r/utils/atomic_file_ops.py

import asyncio
from pathlib import Path
from typing import Optional
import aiofiles
import aiofiles.os

async def atomic_write_with_verification(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    verify_after_write: bool = True,
    max_retries: int = 3
) -> bool:
    """
    原子性写入文件，包含验证和重试机制。
    
    使用临时文件+原子重命名，确保写入的原子性。
    """
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    
    for attempt in range(max_retries):
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入临时文件
            async with aiofiles.open(temp_path, "w", encoding=encoding) as f:
                await f.write(content)
                await f.flush()
            
            # 原子重命名
            await aiofiles.os.replace(str(temp_path), str(file_path))
            
            # 等待文件系统同步
            await asyncio.sleep(0.1)
            
            # 验证文件
            if verify_after_write:
                if not await aiofiles.os.path.exists(str(file_path)):
                    raise FileNotFoundError(f"File does not exist after atomic write: {file_path}")
                
                # 验证内容
                async with aiofiles.open(file_path, "r", encoding=encoding) as f:
                    read_content = await f.read()
                    if read_content != content:
                        raise ValueError(f"File content mismatch after atomic write: {file_path}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Atomic write failed (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                await asyncio.sleep(0.1 * (2 ** attempt))
            else:
                logger.error(f"Atomic write failed after {max_retries} attempts: {e}")
                # 清理临时文件
                if await aiofiles.os.path.exists(str(temp_path)):
                    try:
                        await aiofiles.os.remove(str(temp_path))
                    except Exception:
                        pass
                return False
    
    return False
```

## 实施优先级

### 高优先级（立即实施）
1. ✅ Schedule 更新的并发控制（使用锁）
2. ✅ Timeline CSV 写入的可靠性增强（已完成）
3. ✅ 所有锁的超时机制（部分已完成）

### 中优先级（近期实施）
1. 文件写入的可靠性增强（重试机制）
2. 文件操作的原子性保证（临时文件+重命名）
3. 文件系统同步的等待机制

### 低优先级（长期优化）
1. 文件系统事件监听（watchdog）
2. 乐观锁机制（版本号/时间戳）
3. 死锁检测和恢复机制

## 实施步骤

1. **创建工具模块**：
   - `kat_rec_web/backend/t2r/utils/reliable_file_ops.py`
   - `kat_rec_web/backend/t2r/utils/lock_manager.py`
   - `kat_rec_web/backend/t2r/utils/atomic_file_ops.py`

2. **修改 schedule_service.py**：
   - 添加 schedule 更新锁
   - 创建事务性更新函数

3. **修改 plan.py**：
   - 使用事务性 schedule 更新
   - 使用可靠的文件写入函数

4. **修改 automation.py**：
   - 使用事务性 schedule 更新
   - 使用可靠的文件写入函数

5. **测试和验证**：
   - 并发测试
   - 时序测试
   - 压力测试

