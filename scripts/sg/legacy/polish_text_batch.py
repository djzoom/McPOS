#!/usr/bin/env python3
# coding: utf-8
"""SiG 英文文案打磨环节 — 修拼接伤,保连祷语气,五道后置门。

上游 generate_text_batch.py 的产物由 Whisper 转写原子拼接,携带转写
变体、句号丢失、动词悬空等拼接伤(audit_text_batch.py 负责取证)。
本环节用 LLM 做**保守编辑**——只修伤、不加戏——并以门禁兜底:

  ①重审计零缺陷  ②经文引用集合与原文完全一致  ③人称视角一致
  ④词数在原文 80%–125% 区间  ⑤以 Amen 收尾
  全过才落 polished/,一期一放行,失败即停。

  ./.venv/bin/python scripts/sg/polish_text_batch.py --episodes 1
  ./.venv/bin/python scripts/sg/polish_text_batch.py --episodes 2-10
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_text_batch import audit_text, sentences          # noqa: E402
from translate_text_batch import _BOOK_RE, make_client      # noqa: E402

BATCH_DIR = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                           "sg_toytune_ep1/text_batch_10")
POLISHED_DIR = BATCH_DIR / "polished"
MODEL = "gpt-4o"
MAX_RETRY = 3

SYSTEM_PROMPT = """You are a copy editor for "Sleep in Grace", a Christian
bedtime-prayer channel. The draft below was assembled from speech-to-text
fragments and carries stitching wounds. Repair it into a clean, complete,
recordable script.

HARD RULES
1. FIX every listed defect, plus any other transcription wound you find:
   duplicated variants of the same sentence, missing periods that merged two
   sentences, dangling transitive verbs (add the natural object), lowercase
   sentence starts, doubled word groups, broken logic frames.
2. PRESERVE the voice: slow, quiet, litany-like. Short anaphora fragments
   ("Or think perfectly." / "Even in the waiting.") are intentional style —
   keep them. Do NOT smooth the text into essay prose.
3. PRESERVE every scripture citation exactly (book name, chapter:verse, and
   its quoted wording); write citations as "Book C:V" with a colon.
4. PRESERVE the perspective ({perspective}: {persp_note}) throughout.
5. Do not add new theological content, imagery, or sentences beyond the
   minimal bridging needed to heal a wound. Length stays close to the draft.
6. The closing must end with exactly "Amen."
7. Output plain text for the three sections; no markdown, no notes."""


def citations(text: str) -> set[str]:
    return {f"{m.group(1)} {m.group(2)}:{m.group(3)}"
            for m in _BOOK_RE.finditer(text.replace(".", ":").replace(" :", ":"))} \
        if False else {
        f"{m.group(1)} {m.group(2)}:{m.group(3)}"
        for m in _BOOK_RE.finditer(re.sub(r"(\d+)\.(\d+)", r"\1:\2", text))}


def perspective_violation(text: str, perspective: str) -> str | None:
    body = re.sub(r"\"[^\"]*\"", "", text)          # 引号内豁免
    if perspective == "singular" and re.search(r"\b(we|our|us)\b", body, re.I):
        m = re.search(r"[^.]*\b(we|our|us)\b[^.]*\.", body, re.I)
        return f"单数视角出现复数人称: {m.group(0).strip()[:60] if m else ''}"
    if perspective == "plural":
        # 经文引文里上帝自称「I」不算视角漂移:says/said 所在句起 4 句内、
        # 且句中不含 we/our/us 的,视为引文连续段,豁免。
        sents = re.split(r"(?<=[.!?])\s+", body)
        quote_until = -1
        solo = 0
        for k, sent in enumerate(sents):
            if re.search(r"\b(says|said)\b", sent):
                quote_until = k + 4
            in_quote = k <= quote_until and \
                not re.search(r"\b(we|our|us)\b", sent, re.I)
            if not in_quote and re.search(r"\bI\b", sent):
                solo += 1
        if solo > 2:
            return f"复数视角出现 {solo} 处引文外单数「I」"
    return None


SCHEMA = {
    "type": "object",
    "properties": {"opening": {"type": "string"},
                   "prayer": {"type": "string"},
                   "closing": {"type": "string"}},
    "required": ["opening", "prayer", "closing"],
    "additionalProperties": False,
}


def polish_episode(client, n: int, defects: list[dict]) -> dict:
    src = json.loads((BATCH_DIR / f"sg_text_ep{n:02d}.json").read_text())
    eid, perspective = src["episode_id"], src["qa"]["perspective"]
    sec = {"opening": [], "prayer": [], "closing": []}
    for a in src["plan"]:
        sec[a["section"]].append(a["text"].strip())
    draft = {k: " ".join(v) for k, v in sec.items()}
    src_words = sum(len(v.split()) for v in draft.values())
    src_cites = citations(" ".join(draft.values()))

    persp_note = ("first-person singular (I/my)" if perspective == "singular"
                  else "first-person plural (we/our)")
    sys_p = SYSTEM_PROMPT.format(perspective=perspective, persp_note=persp_note)
    feedback = ""
    for attempt in range(1, MAX_RETRY + 1):
        user = {"draft": draft,
                "defects_found_by_audit": [
                    {"type": d["type"], "sentence": d["text"], "note": d["note"]}
                    for d in defects]}
        if feedback:
            user["previous_attempt_failed_gates"] = feedback
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": sys_p},
                      {"role": "user",
                       "content": json.dumps(user, ensure_ascii=False)}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": "polished", "strict": True,
                                             "schema": SCHEMA}},
            temperature=0.3,
        )
        out = json.loads(resp.choices[0].message.content)
        full = " ".join(out[k] for k in ("opening", "prayer", "closing"))
        gates: list[str] = []
        re_defects = audit_text(full)
        if re_defects:
            gates.append("重审计仍有缺陷: " + "; ".join(
                f"[{d['type']}] {d['text'][:40]}" for d in re_defects[:5]))
        new_cites = citations(full)
        if new_cites != src_cites:
            gates.append(f"经文引用集合改变: 原 {sorted(src_cites)} → "
                         f"现 {sorted(new_cites)}")
        pv = perspective_violation(full, perspective)
        if pv:
            gates.append(pv)
        words = len(full.split())
        if not (0.80 * src_words <= words <= 1.25 * src_words):
            gates.append(f"词数越界: {words}(原 {src_words})")
        if not out["closing"].rstrip().endswith("Amen."):
            gates.append(f"结尾不是 Amen.: …{out['closing'].rstrip()[-30:]}")
        if not gates:
            return {"ok": True, "episode_id": eid, "perspective": perspective,
                    "sections": out, "word_count": words,
                    "source_word_count": src_words,
                    "citations": sorted(new_cites),
                    "defects_fixed": len(defects)}
        feedback = "; ".join(gates)
        print(f"    第 {attempt} 次未过: {feedback[:120]}", flush=True)
        time.sleep(1.5)
    return {"ok": False, "episode_id": eid, "error": feedback}


def render_md(res: dict) -> str:
    s = res["sections"]
    out = [f"# {res['episode_id']} · polished", "",
           "QA: `PASS`(audit-zero / citations / perspective / length / Amen)",
           f"Perspective: `{res['perspective']}`  ",
           f"Words: `{res['word_count']}`(source {res['source_word_count']})  ",
           f"Citations: `{', '.join(res['citations']) or '—'}`  ",
           f"Defects fixed: `{res['defects_fixed']}`", ""]
    for k, title in (("opening", "Opening"), ("prayer", "Prayer"),
                     ("closing", "Closing")):
        out += [f"## {title}", "", s[k].strip(), ""]
    return "\n".join(out)


def validate_external(n: int, sections: dict, defects: list[dict]) -> dict:
    """--from-json 入口:编辑由外部(人工/会话内模型)完成,门禁照跑。"""
    src = json.loads((BATCH_DIR / f"sg_text_ep{n:02d}.json").read_text())
    eid, perspective = src["episode_id"], src["qa"]["perspective"]
    sec = {"opening": [], "prayer": [], "closing": []}
    for a in src["plan"]:
        sec[a["section"]].append(a["text"].strip())
    draft = {k: " ".join(v) for k, v in sec.items()}
    src_words = sum(len(v.split()) for v in draft.values())
    src_cites = citations(" ".join(draft.values()))

    full = " ".join(sections[k] for k in ("opening", "prayer", "closing"))
    gates: list[str] = []
    re_defects = audit_text(full)
    if re_defects:
        gates.append("重审计仍有缺陷: " + "; ".join(
            f"[{d['type']}] {d['text'][:50]} ← {d['note'][:30]}"
            for d in re_defects[:6]))
    new_cites = citations(full)
    if new_cites != src_cites:
        gates.append(f"经文引用集合改变: 原 {sorted(src_cites)} → 现 {sorted(new_cites)}")
    pv = perspective_violation(full, perspective)
    if pv:
        gates.append(pv)
    words = len(full.split())
    if not (0.80 * src_words <= words <= 1.25 * src_words):
        gates.append(f"词数越界: {words}(原 {src_words})")
    if not sections["closing"].rstrip().endswith("Amen."):
        gates.append("结尾不是 Amen.")
    if gates:
        return {"ok": False, "episode_id": eid, "error": " | ".join(gates)}
    return {"ok": True, "episode_id": eid, "perspective": perspective,
            "sections": sections, "word_count": words,
            "source_word_count": src_words, "citations": sorted(new_cites),
            "defects_fixed": len(defects)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="1")
    ap.add_argument("--from-json", type=Path, default=None,
                    help="外部供稿 {opening,prayer,closing};门禁照跑,过则落盘")
    a = ap.parse_args()
    nums = (list(range(int(a.episodes.split("-")[0]),
                       int(a.episodes.split("-")[1]) + 1))
            if "-" in a.episodes else [int(a.episodes)])

    report_path = BATCH_DIR / "english_audit_report.json"
    audit = json.loads(report_path.read_text()) if report_path.exists() else {}
    client = None if a.from_json else make_client()
    POLISHED_DIR.mkdir(exist_ok=True)

    for n in nums:
        defects = audit.get(f"ep{n:02d}", [])
        print(f"— ep{n:02d}: {len(defects)} 处已知缺陷,打磨中…", flush=True)
        t0 = time.time()
        if a.from_json:
            res = validate_external(n, json.loads(a.from_json.read_text()),
                                    defects)
        else:
            res = polish_episode(client, n, defects)
        if not res["ok"]:
            print(f"⛔ {res['episode_id']} FAIL: {res['error'][:200]}")
            print("   (一期未过即停;修复后从该期重跑)")
            return 1
        eid = res["episode_id"]
        (POLISHED_DIR / f"{eid}.md").write_text(render_md(res), encoding="utf-8")
        payload = dict(res)
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        payload["model"] = "claude-session-edit" if a.from_json else MODEL
        payload["sentences"] = {k: sentences(res["sections"][k])
                                for k in ("opening", "prayer", "closing")}
        (POLISHED_DIR / f"{eid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ {eid} PASS({res['word_count']} 词, "
              f"{time.time() - t0:.0f}s)→ polished/{eid}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
