#!/usr/bin/env python3
"""Read WSJ·NYT briefing JSON, generate Korean summaries via the
Anthropic Messages API, and post the briefing to Slack #wsj-nyt.

Reads:  data/briefing/wsj-nyt-YYYY-MM-DD.json
Writes: posts a single message to Slack via chat.postMessage
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
TODAY_STR = datetime.now(KST).strftime("%Y-%m-%d")
DATA_PATH = os.environ.get(
    "BRIEFING_DATA_PATH", f"data/briefing/wsj-nyt-{TODAY_STR}.json"
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "C0B13399JG3")

if not SLACK_TOKEN:
    print("ERROR: SLACK_TOKEN missing", file=sys.stderr)
    sys.exit(1)

with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)

ARTICLES = data["articles"]
DATE = data["date"]


# ── Anthropic helper ────────────────────────────────────────────────
def claude(prompt: str, max_tokens: int = 300) -> str:
    if not ANTHROPIC_API_KEY:
        return ""
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        parts = out.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    except Exception as e:
        print(f"[warn] Anthropic call failed: {e}", file=sys.stderr)
        return ""


def korean_title(en_title: str) -> str:
    if not en_title:
        return ""
    txt = claude(
        "다음 영문 기사 제목을 자연스러운 한국어로 한 줄 번역. "
        "40자 이하, 따옴표·설명 빼고 번역만 출력.\n\n"
        f"원문: {en_title}\n번역:",
        max_tokens=80,
    )
    return txt.strip().strip('"').strip("'")


def korean_summary(article: dict) -> str:
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    if not abstract:
        return ""
    return claude(
        "다음 영문 기사를 한국어 핵심 3줄로 요약 (각 줄 60자 이하, 대시 - 로 시작, 사실만, 광고체 금지):\n\n"
        f"제목: {title}\n요약: {abstract}\n\n3줄 요약:",
        max_tokens=240,
    )


# ── Selection logic ─────────────────────────────────────────────────
def jimmy_priority(a: dict) -> int:
    tags = a.get("interest_tags", [])
    p = 0
    if "AI" in tags:
        p += 4
    if "보안" in tags:
        p += 3
    if "재무" in tags:
        p += 3
    if "신앙" in tags:
        p += 2
    if "국제" in tags:
        p += 1
    return p


def access_emoji(access: str) -> str:
    return "🔓무료" if access == "free" else "🔒구독"


def tag_emoji(a: dict) -> str:
    s = a.get("controversy_score", 0)
    if s >= 50:
        return "🔥논란"
    if s >= 5:
        return "📈인기"
    return "💡인사이트"


# Top 10 selection — score first, then NYT MostPopular, then interest match
def select_top_10(articles: list) -> list:
    sorted_articles = sorted(
        articles,
        key=lambda a: (
            -a.get("controversy_score", 0),
            -(1 if any(
                k in a.get("rank_kinds", []) for k in ("viewed", "shared_fb", "emailed")
            ) else 0),
            -jimmy_priority(a),
        ),
    )
    return sorted_articles[:10]


TOP10 = select_top_10(ARTICLES)
PICK_A = TOP10[0] if TOP10 else None
PICK_B = max(ARTICLES, key=jimmy_priority) if ARTICLES else None
# Avoid picking the same article for both
if PICK_A and PICK_B and PICK_A.get("url") == PICK_B.get("url"):
    candidates = [a for a in ARTICLES if a.get("url") != PICK_A.get("url")]
    if candidates:
        PICK_B = max(candidates, key=jimmy_priority)


# ── Korean translation pass ─────────────────────────────────────────
print(f"[info] translating {len(TOP10)} top titles + summaries...", file=sys.stderr)
for a in TOP10:
    a["ko_title"] = korean_title(a["title"]) or a["title"]
    a["ko_summary"] = korean_summary(a)
if PICK_B and PICK_B not in TOP10:
    PICK_B["ko_title"] = korean_title(PICK_B["title"]) or PICK_B["title"]
    PICK_B["ko_summary"] = korean_summary(PICK_B)


# ── Build message ───────────────────────────────────────────────────
lines = [f"📰 *{DATE} | WSJ·NYT 브리핑*", ""]

# Pick B — Jimmy 추천 (top of message)
if PICK_B:
    relate = ", ".join(PICK_B.get("interest_tags", [])) or "일반"
    lines.append("💡 *오늘의 픽 B — Jimmy님 추천*")
    lines.append(f"<{PICK_B['url']}|{PICK_B.get('ko_title') or PICK_B['title']}>")
    lines.append(f"_{PICK_B['title']}_")
    lines.append(
        f"• 출처: {PICK_B['source']} / {PICK_B.get('section', '')} | 관련: {relate}"
    )
    if PICK_B.get("ko_summary"):
        lines.append(PICK_B["ko_summary"])
    if ANTHROPIC_API_KEY:
        connect = claude(
            "Jimmy님은 50대 개발자로 Claude Code 자동화·은퇴/연금 설계·신앙 QT·사이버보안에 관심이 많습니다. "
            "다음 기사를 Jimmy님의 현재 작업과 연결지어 실무 적용 포인트를 한국어 1줄(50자 이하)로 제안:\n\n"
            f"제목: {PICK_B['title']}\n요약: {PICK_B.get('abstract', '')}",
            max_tokens=120,
        )
        if connect:
            lines.append(f"🎯 _{connect}_")
    lines.append("")

# Pick A — 논란
if PICK_A and PICK_A.get("controversy_score", 0) > 0:
    lines.append("🔥 *오늘의 논란 픽 A*")
    lines.append(f"<{PICK_A['url']}|{PICK_A.get('ko_title') or PICK_A['title']}>")
    lines.append(f"_{PICK_A['title']}_")
    r = PICK_A.get("reddit", {})
    h = PICK_A.get("hn", {})
    lines.append(
        f"• 논란지수: {PICK_A['controversy_score']:.0f}점 | "
        f"Reddit {r.get('upvotes', 0)}↑ {r.get('comments', 0)}💬 | "
        f"HN {h.get('points', 0)}pt {h.get('comments', 0)}💬"
    )
    if PICK_A.get("ko_summary"):
        lines.append(PICK_A["ko_summary"])
    if ANTHROPIC_API_KEY:
        why = claude(
            "다음 기사가 Reddit/HN에서 강한 반응을 일으킨 이유를 한국어 2문장으로 설명:\n"
            f"제목: {PICK_A['title']}\n요약: {PICK_A.get('abstract', '')}\n"
            f"Reddit 댓글 {r.get('comments', 0)}, upvote {r.get('upvotes', 0)}, "
            f"HN {h.get('points', 0)}pt",
            max_tokens=200,
        )
        if why:
            lines.append(f"› {why}")
    lines.append("")

# Top 10 list — split NYT / WSJ
lines.append("📋 *전체 기사 Top 10*")
nyt_items = [a for a in TOP10 if a["source"] == "NYT"]
wsj_items = [a for a in TOP10 if a["source"] == "WSJ"]

if nyt_items:
    lines.append("*NYT*")
    for i, a in enumerate(nyt_items, 1):
        title = a.get("ko_title") or a["title"]
        sec = a.get("section", "") or "—"
        score = a.get("controversy_score", 0)
        lines.append(
            f"{i}. <{a['url']}|{title}> · `{sec}` · "
            f"{access_emoji(a['access'])} · {tag_emoji(a)} · 논란{score:.0f}"
        )

if wsj_items:
    lines.append("*WSJ*")
    for i, a in enumerate(wsj_items, 1):
        title = a.get("ko_title") or a["title"]
        sec = a.get("section", "") or "—"
        score = a.get("controversy_score", 0)
        lines.append(
            f"{i}. <{a['url']}|{title}> · `{sec}` · "
            f"{access_emoji(a['access'])} · {tag_emoji(a)} · 논란{score:.0f}"
        )

lines.append("")

# Execution summary
nyt_total = sum(1 for a in ARTICLES if a["source"] == "NYT")
wsj_total = sum(1 for a in ARTICLES if a["source"] == "WSJ")
hn_match = sum(1 for a in ARTICLES if a.get("hn"))
red_match = sum(1 for a in ARTICLES if a.get("reddit"))

lines.append("```")
lines.append("================================")
lines.append("📊 WSJ·NYT 브리핑 실행 완료")
lines.append("================================")
lines.append(f"실행 시각      : {data['generated_at']}")
lines.append(f"NYT 수집       : {nyt_total}개")
lines.append(f"WSJ 수집       : {wsj_total}개")
lines.append(f"Reddit 교차    : {red_match}개")
lines.append(f"HN 교차        : {hn_match}개")
lines.append(f"최종 선별      : {len(TOP10)}개")
lines.append("================================")
lines.append("```")

text = "\n".join(lines)

# Optional preview write for debugging
preview_path = os.environ.get("PREVIEW_PATH")
if preview_path:
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[info] preview saved → {preview_path}", file=sys.stderr)


# ── Post to Slack ───────────────────────────────────────────────────
print(f"[info] posting to Slack channel {SLACK_CHANNEL}...", file=sys.stderr)
body = json.dumps({
    "channel": SLACK_CHANNEL,
    "text": text,
    "unfurl_links": False,
    "unfurl_media": False,
}).encode("utf-8")
req = urllib.request.Request(
    "https://slack.com/api/chat.postMessage",
    data=body,
    headers={
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {SLACK_TOKEN}",
    },
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        print(f"[err] Slack API: {result}", file=sys.stderr)
        sys.exit(1)
    print(f"[done] message_ts={result.get('ts')}", file=sys.stderr)
except Exception as e:
    print(f"[err] Slack post: {e}", file=sys.stderr)
    sys.exit(1)
