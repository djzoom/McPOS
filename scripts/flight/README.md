# 空中名所 · 木刻版画飞行动画

飞机或飞鸟低空掠过八处风景，画面做成彩色水印木刻：
墨线主版、限色色版、暈し（bokashi）渐变、木纹与胡麻摺，和纸纹理、题签与朱印。

| 景名 `--scenes` | 地方 | 特征 | 默认飞行物 |
|---|---|---|---|
| `niigata` | 新潟 | 水田、樱花、朱漆桥 | 丹顶鹤 |
| `tuscany` | 托斯卡纳·圣吉米尼亚诺 | 城墙古城与塔楼、葡萄园、柏树大道、橄榄林 | 小飞机 |
| `serengeti` | 塞伦盖蒂 | 长草、角马群、池塘、金合欢 | 小飞机 |
| `bruges` | 布鲁日 | 护城河环绕的砖顶古城、运河、风车、天鹅 | 雁阵 |
| `pampa` | 潘帕斯 | 草原、牛群、农舍 | 双翼机 |
| `provence` | 普罗旺斯·戈尔德 | 石头村、薰衣草条田、麦田 | 双翼机 |
| `punjab` | 旁遮普 | 芥菜花田、水渠、林地 | 雁阵 |
| `krumlov` | 克鲁姆洛夫 | 河湾古城、城堡塔、森林、河上小船 | 白鹳 |

飞行物 `--flyer`：`auto`（按上表）/ `plane` / `biplane` / `jet` / `crane` / `stork` / `geese`，
逗号分隔则逐景轮换（如 `--flyer crane,geese`）。鸟会扇翅，双翼机螺旋桨会转。

古城每 150 m 出现一座（每景约 45 秒能飞过一座），房屋是真正的坡顶体块，沿扭曲的街区
四边排布，中心广场放地标（主教座堂、钟楼、城堡），有影子、有墨线。

| 文件 | 职责 |
|---|---|
| `flight.html` | 渲染引擎（Three.js r128，CDN 加载）。直接用浏览器打开即是实时预览 |
| `render_flight.py` | 无头 Chromium 逐帧驱动引擎 → ffmpeg → 16:9 H.264 MP4 |

```bash
./.venv/bin/python scripts/flight/render_flight.py --res 4k    --duration 10m --out ~/Desktop/flight_4k.mp4
./.venv/bin/python scripts/flight/render_flight.py --res 256   --duration 30  --out /tmp/tiny.mp4
./.venv/bin/python scripts/flight/render_flight.py --res 1080p --duration 3h --unique 20m --labels none --out long.mp4
```

- `--res`：`4k/1440p/1080p/720p/480p/360p/240p/144p`，或宽度 256–3840（高度按 16:9 取偶数）
- `--duration`：`90` / `10m` / `1h30m` / `01:30:00`
- `--segment`：每景秒数（默认 45，自动微调到整除总时长）；`--scenes` 景序（逗号分隔）；`--seed` 换一套地形
- `--labels zh|en|none`：中文竖排题签 / 英文题签 / 无
- `--unique`：只渲染这么长的不重样片段，再无缝循环铺满总时长。每景都从空白纸面淡入、
  淡出回纸面，所以循环接缝不可见；拼接用 `-c copy`，不重编码
- 依赖：`playwright`（已在 requirements.txt，首次需 `playwright install chromium`）与 `ffmpeg`
- 离线：`--three path/to/three.min.js`（r128）

**确定性**：时间由帧号推导、所有随机数带种子，同一组参数永远出同一部片。
**分辨率无关**：墨线、木纹、纸纹都按世界单位计算，256 与 4K 构图一致；细于一个像素的
细节（胡麻摺、草叶刀痕、水纹）按像素尺度自动淡出，低分辨率不闪烁。

**速度**：耗时几乎全在 GPU。无 GPU 的云容器（SwiftShader 软件渲染）实测
1080p 约 0.6 帧/秒、256 宽约 6 帧/秒；有 GPU 的机器会快得多。长片优先用 `--unique`。
