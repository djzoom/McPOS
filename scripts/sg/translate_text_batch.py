#!/usr/bin/env python3
# coding: utf-8
"""SiG 十期文案翻译管线(修复版)— 结构化输出 + 十道门禁。

对应 TRANSLATION_QA_FAILURE_MEMO.md 的整改要求:上一轮失败的根因是
翻译循环把 LLM 原始响应(列表 repr/字典串/JSON 片段/指令回声)未经
校验直接写入文件,且 `PASS` 只数了原子数量。本管线:

  引擎     OpenAI Structured Outputs(json_schema strict)——形状由 API 保证,
           不靠正则去捞;批内附带前文语境 + 术语表,保证人称与用词一致。
  门禁     memo 十条全部代码化(见 gate_atom / gate_episode):
           ①纯字符串 ②禁残留英文 ③1:1 对齐 ④人称 ⑤经文书卷/章节/数字
           ⑥否定词保留 ⑦Amen=阿们 ⑧简体全过才转繁体(OpenCC s2twp)
           ⑨全门通过才 PASS ⑩每次只放行一期,失败即停。
  重试     失败原子单独重译(附失败原因),3 次不过 → 该期 FAIL 停批。

  ./.venv/bin/python scripts/sg/translate_text_batch.py --episodes 1
  ./.venv/bin/python scripts/sg/translate_text_batch.py --episodes 2-10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BATCH_DIR = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                           "sg_toytune_ep1/text_batch_10")
OUT_DIR = BATCH_DIR / "translations"
ROOT = Path(__file__).resolve().parents[2]

MODEL_CANDIDATES = ["gpt-4o", "gpt-4o-mini"]
BATCH_SIZE = 18
MAX_RETRY = 3

GLOSSARY = {
    "God": "上帝", "Lord": "主", "Jesus": "耶稣", "Christ": "基督",
    "Holy Spirit": "圣灵", "Amen": "阿们", "Sleep in Grace": "安睡于恩典",
}

BOOKS = {
    "Genesis": "创世记", "Exodus": "出埃及记", "Leviticus": "利未记",
    "Numbers": "民数记", "Deuteronomy": "申命记", "Joshua": "约书亚记",
    "Judges": "士师记", "Ruth": "路得记", "1 Samuel": "撒母耳记上",
    "2 Samuel": "撒母耳记下", "1 Kings": "列王纪上", "2 Kings": "列王纪下",
    "Job": "约伯记", "Psalm": "诗篇", "Psalms": "诗篇", "Proverbs": "箴言",
    "Ecclesiastes": "传道书", "Isaiah": "以赛亚书", "Jeremiah": "耶利米书",
    "Lamentations": "耶利米哀歌", "Ezekiel": "以西结书", "Daniel": "但以理书",
    "Hosea": "何西阿书", "Joel": "约珥书", "Micah": "弥迦书",
    "Zephaniah": "西番雅书", "Zechariah": "撒迦利亚书", "Malachi": "玛拉基书",
    "Matthew": "马太福音", "Mark": "马可福音", "Luke": "路加福音",
    "John": "约翰福音", "Acts": "使徒行传", "Romans": "罗马书",
    "1 Corinthians": "哥林多前书", "2 Corinthians": "哥林多后书",
    "Galatians": "加拉太书", "Ephesians": "以弗所书", "Philippians": "腓立比书",
    "Colossians": "歌罗西书", "1 Thessalonians": "帖撒罗尼迦前书",
    "2 Thessalonians": "帖撒罗尼迦后书", "1 Timothy": "提摩太前书",
    "2 Timothy": "提摩太后书", "Titus": "提多书", "Hebrews": "希伯来书",
    "James": "雅各书", "1 Peter": "彼得前书", "2 Peter": "彼得后书",
    "1 John": "约翰一书", "Jude": "犹大书", "Revelation": "启示录",
}
_BOOK_RE = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in sorted(BOOKS, key=len, reverse=True))
    + r")\s+(\d+)\s*:\s*(\d+)")
_NEG_RE = re.compile(r"\b(not|never|no|nothing|none|neither|nor|don't|doesn't|"
                     r"won't|cannot|can't|isn't|aren't)\b", re.I)
_ZH_NEG_RE = re.compile(r"[不没別别勿无無非莫未]")

SYSTEM_PROMPT = """你是资深的基督教灵修文本译者,把英文晚祷逐句译成简体中文。

铁律:
1. 逐条翻译,每条输出一个纯中文字符串——绝不输出英文、拼音、列表、
   字典、JSON、引号包裹或任何解释。
2. 术语表(必须遵守): God=上帝, Lord=主, Jesus=耶稣, Christ=基督,
   Holy Spirit=圣灵, Amen=阿们, Sleep in Grace=安睡于恩典。
3. 圣经引用: 书卷名用和合本中文名(如 Deuteronomy 31:6 = 申命记 31:6),
   章节数字原样保留;经文语义按和合本措辞,不缩译、不漏否定词。
4. 人称: I/my/me=我/我的; we/our/us=我们/我们的; 祷告中指向上帝的
   you/your 译为"你/你的"(本频道不用"祢")。视角是 {perspective}
   ({persp_note}),全篇保持一致。
5. not/never/no 等否定语义必须保留。
6. 语气:安静、缓慢、适合睡前朗读;句子短;句号结尾。
7. 这是连续祷告文的一部分,保持与前文(context)的语气与人称衔接。"""


def log(msg: str) -> None:
    print(msg, flush=True)


# ------------------------------------------------------------------ 门禁 ---

def gate_atom(en: str, zh: str, perspective: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(zh, str) or not zh.strip():
        return ["空翻译"]
    zh = zh.strip()
    if re.search(r"[\[\]{}<>/|=_]|[\"']\s*:|译文|translation|Chinese", zh):
        errs.append(f"结构字符残留: {zh[:40]}")
    if re.search(r"[A-Za-z]{2,}", zh):
        errs.append(f"英文残留: {zh[:60]}")
    if _NEG_RE.search(en) and not _ZH_NEG_RE.search(zh):
        errs.append(f"否定词丢失: '{en[:40]}' → '{zh[:40]}'")
    if re.fullmatch(r"\s*amen[.!]?\s*", en, re.I) and zh not in ("阿们。", "阿们"):
        errs.append(f"Amen 必须译为「阿们。」,得到: {zh}")
    m = _BOOK_RE.search(en)
    if m:
        book, ch, vs = m.group(1), m.group(2), m.group(3)
        if BOOKS[book] not in zh:
            errs.append(f"经文书卷缺失: 应含「{BOOKS[book]}」: {zh[:50]}")
        if not (ch in zh and vs in zh):
            errs.append(f"经文章节数字缺失({ch}:{vs}): {zh[:50]}")
    if perspective == "singular" and re.search(r"我们|我們|咱们", zh):
        errs.append(f"单数视角出现「我们」: {zh[:40]}")
    return errs


def gate_episode(pairs: list[dict], perspective: str) -> list[str]:
    errs = []
    ids = [p["id"] for p in pairs]
    if len(ids) != len(set(ids)):
        errs.append("原子 id 重复")
    last_zh = pairs[-1]["zh"].strip() if pairs else ""
    if "阿们" not in last_zh:
        errs.append(f"最后一条不是阿们收尾: {last_zh[:30]}")
    return errs


# ------------------------------------------------------------- 翻译引擎 ---

def make_client():
    from openai import OpenAI
    key = None
    cfg = ROOT / "config" / "api_config.json"
    if cfg.exists():
        key = json.loads(cfg.read_text()).get("keys", {}).get("openai")
    return OpenAI(api_key=key) if key else OpenAI()


SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"},
                               "zh": {"type": "string"}},
                "required": ["id", "zh"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def call_llm(client, model: str, perspective: str, context: str,
             batch: list[dict], feedback: str = "") -> dict[str, str]:
    persp_note = ("第一人称单数祷告(我)" if perspective == "singular"
                  else "第一人称复数祷告(我们)")
    sys_p = SYSTEM_PROMPT.format(perspective=perspective, persp_note=persp_note)
    user = {"context_前文最后几句": context,
            "atoms": [{"id": a["id"], "en": a["text"]} for a in batch]}
    if feedback:
        user["上一次的错误必须修正"] = feedback
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": sys_p},
                  {"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "translations", "strict": True,
                                         "schema": SCHEMA}},
        temperature=0.2,
    )
    data = json.loads(resp.choices[0].message.content)
    return {it["id"]: it["zh"].strip() for it in data["items"]}


def translate_episode(client, model: str, ep_json: Path) -> dict:
    src = json.loads(ep_json.read_text())
    eid = src["episode_id"]
    perspective = src["qa"]["perspective"]
    atoms = [{"id": a["id"], "text": a["text"], "section": a["section"]}
             for a in src["plan"]]
    log(f"— {eid}: {len(atoms)} 原子, 视角 {perspective}")

    zh_map: dict[str, str] = {}
    context = ""
    for i in range(0, len(atoms), BATCH_SIZE):
        batch = atoms[i:i + BATCH_SIZE]
        feedback = ""
        for attempt in range(1, MAX_RETRY + 1):
            got = call_llm(client, model, perspective, context, batch, feedback)
            missing = [a["id"] for a in batch if a["id"] not in got]
            errors: dict[str, list[str]] = {}
            for a in batch:
                if a["id"] in got:
                    e = gate_atom(a["text"], got[a["id"]], perspective)
                    if e:
                        errors[a["id"]] = e
            if not missing and not errors:
                for a in batch:
                    zh_map[a["id"]] = got[a["id"]]
                break
            feedback = json.dumps(
                {"缺失": missing,
                 "未过门禁": {k: v for k, v in errors.items()}},
                ensure_ascii=False)
            log(f"    批 {i // BATCH_SIZE + 1} 第 {attempt} 次未过: "
                f"缺失 {len(missing)} 错误 {len(errors)}")
            time.sleep(1.5)
        else:
            return {"ok": False, "episode_id": eid,
                    "error": f"批 {i // BATCH_SIZE + 1} 重试 {MAX_RETRY} 次仍未过门禁",
                    "detail": feedback}
        context = "".join(zh_map[a["id"]] for a in batch[-3:])

    pairs = [{"id": a["id"], "section": a["section"], "en": a["text"],
              "zh": zh_map[a["id"]]} for a in atoms]
    ep_errs = gate_episode(pairs, perspective)
    if ep_errs:
        return {"ok": False, "episode_id": eid, "error": "; ".join(ep_errs)}

    # ⑧ 简体全过 → 繁体(确定性转换)
    from opencc import OpenCC
    cc = OpenCC("s2twp")
    for p in pairs:
        p["zh_tw"] = cc.convert(p["zh"])

    return {"ok": True, "episode_id": eid, "perspective": perspective,
            "pairs": pairs}


# --------------------------------------------------------------- 渲染 ---

SECTION_TITLES = {"opening": "开场", "prayer": "祷告", "closing": "结尾"}
SECTION_TITLES_TW = {"opening": "開場", "prayer": "禱告", "closing": "結尾"}


def render_md(eid: str, pairs: list[dict], perspective: str, tw: bool) -> str:
    titles = SECTION_TITLES_TW if tw else SECTION_TITLES
    key = "zh_tw" if tw else "zh"
    lang = "繁體中文" if tw else "简体中文"
    out = [f"# {eid} · {lang}", "",
           f"翻譯 QA: `PASS`" if tw else "翻译 QA: `PASS`",
           f"視角: `{perspective}`" if tw else f"视角: `{perspective}`",
           f"原子數: `{len(pairs)}`" if tw else f"原子数: `{len(pairs)}`", ""]
    for section in ("opening", "prayer", "closing"):
        seg = [p[key] for p in pairs if p["section"] == section]
        if not seg:
            continue
        out += [f"## {titles[section]}", "", "".join(seg), ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="SiG 文案翻译管线(十道门禁)")
    ap.add_argument("--episodes", default="1",
                    help="如 1 / 3 / 2-10(⑩每次只放行一期,失败即停)")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()

    if "-" in a.episodes:
        lo, hi = a.episodes.split("-")
        nums = list(range(int(lo), int(hi) + 1))
    else:
        nums = [int(a.episodes)]

    client = make_client()
    model = a.model or MODEL_CANDIDATES[0]
    OUT_DIR.mkdir(exist_ok=True)

    for n in nums:
        ep_json = BATCH_DIR / f"sg_text_ep{n:02d}.json"
        if not ep_json.exists():
            log(f"⛔ 缺 {ep_json.name}")
            return 1
        t0 = time.time()
        res = translate_episode(client, model, ep_json)
        if not res["ok"]:
            log(f"⛔ {res['episode_id']} FAIL: {res['error']}")
            log("   (⑩ 一期未过即停批;修复后从该期重跑)")
            return 1
        eid, pairs = res["episode_id"], res["pairs"]
        (OUT_DIR / f"{eid}.zh-CN.md").write_text(
            render_md(eid, pairs, res["perspective"], tw=False), encoding="utf-8")
        (OUT_DIR / f"{eid}.zh-TW.md").write_text(
            render_md(eid, pairs, res["perspective"], tw=True), encoding="utf-8")
        (OUT_DIR / f"{eid}.translations.json").write_text(json.dumps({
            "episode_id": eid, "source": str(ep_json),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": model, "perspective": res["perspective"],
            "qa": {"ok": True, "gates": "structure/english/1to1/perspective/"
                                        "scripture/negation/amen/ending 全过",
                   "atom_count": len(pairs)},
            "pairs": pairs,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"✅ {eid} PASS({len(pairs)} 原子, {time.time() - t0:.0f}s)"
            f" → {eid}.zh-CN.md / .zh-TW.md / .translations.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
