# 🔧 修复账号错误上传问题

## ❌ 问题描述

视频 `kat_20260201` 被错误地上传到了错误的账号：
- **错误账号**: 0xGarfield (@djwangzhong)
- **视频ID**: 4b7sQPvdhDs
- **正确账号**: @KatRecordsStudio
- **正确频道ID**: UCbLYx6UscJjfZ7Ch9U53nRg

## 🔧 修复步骤

### 步骤 1: 重新授权OAuth（使用正确账号）

运行重新授权脚本：

```bash
python3 scripts/reauthorize_kat_records_studio.py
```

**⚠️ 重要提示**：
- 脚本会打开浏览器进行OAuth授权
- **必须选择 @KatRecordsStudio 账号**
- 如果浏览器中已登录了错误的账号，请先退出登录
- 然后重新运行脚本，选择正确的账号

脚本会自动：
1. 备份旧的错误token
2. 启动OAuth授权流程
3. 验证授权到的账号是否正确
4. 如果账号正确，保存新的token

### 步骤 2: 删除错误账号上的视频（可选）

如果需要删除错误账号上的视频，需要先临时授权到错误账号：

```bash
# 临时恢复错误账号的token（如果需要）
mv config/google/youtube_token.json.backup_0xgarfield config/google/youtube_token.json

# 删除错误视频
python3 scripts/delete_youtube_video.py 4b7sQPvdhDs

# 删除后，重新授权到正确账号（步骤1）
```

### 步骤 3: 重新上传视频到正确账号

确保已授权到正确账号后，重新上传：

```bash
python3 scripts/uploader/upload_to_youtube.py \
    --episode kat_20260201 \
    --video channels/kat/output/kat_20260201/kat_20260201_youtube.mp4
```

## ✅ 已执行的操作

1. ✅ 已备份错误的token文件到 `config/google/youtube_token.json.backup_0xgarfield`
2. ✅ 已创建重新授权脚本 `scripts/reauthorize_kat_records_studio.py`

## 🔍 验证修复

运行以下命令验证当前使用的账号：

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts/uploader')
from upload_to_youtube import load_config, get_authenticated_service

config = load_config()
youtube = get_authenticated_service(config)

response = youtube.channels().list(part='id,snippet', mine=True).execute()
if response.get('items'):
    channel = response['items'][0]
    snippet = channel.get('snippet', {})
    print(f'当前账号: {snippet.get(\"customUrl\", \"N/A\")}')
    print(f'频道名称: {snippet.get(\"title\", \"N/A\")}')
    if '@KatRecordsStudio' in snippet.get('customUrl', ''):
        print('✅ 账号正确！')
    else:
        print('❌ 账号错误，请重新授权')
"
```

## 📝 注意事项

1. **OAuth授权**：确保在浏览器中选择正确的账号
2. **Token文件**：错误的token已备份，可以随时恢复（如果需要）
3. **视频删除**：删除错误账号上的视频需要先授权到该账号
4. **重新上传**：确保使用正确的账号token后再上传

## 🎯 预期结果

修复完成后：
- ✅ OAuth token绑定到 @KatRecordsStudio 账号
- ✅ 视频上传到正确的频道
- ✅ 可以在 https://studio.youtube.com/channel/UCbLYx6UscJjfZ7Ch9U53nRg 看到视频
