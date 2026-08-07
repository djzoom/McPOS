# 退役脚本(2026-08-06)

这些是被取代的旧实现,保留以备追溯,**不在管线里**。
当前管线见上级目录的 VO_PIPELINE.md。

| 退役 | 被谁取代 | 原因 |
|---|---|---|
| harvest_atoms.py / harvest_atoms_v2.py | harvest_whisper.py | 前两代切分器,无词级时间戳、无角色分类 |
| audit_atom_library.py | verify_atom_texts.py | 逐条起 whisper 进程(慢 10 倍),且幻听时保留旧文本 —— 正是 418 条静音带假文本的成因 |
| qc_vo.py | qc_session.py | 只验音频不验文案;整轨转写会招 whisper 复读幻觉 |
| render_vo.py | build_session.build_vo_track | 后者带缓存与真实时间轴 |
| generate_text_batch.py / polish_text_batch.py / audit_text_batch.py / rebuild_atom_faithful.py / realize_from_atoms.py | build_session.py | 旧的「先写文案再找原子」流程;现在是直接从原子编排,文案由构造可实现 |
| render_session_video.py | render_rings_long.py | 单张背景慢推,无音频驱动 |
