#!/usr/bin/env python3
"""Convert briefing data to Slack mrkdwn + Block Kit and post."""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
if not SLACK_TOKEN:
    print("ERROR: SLACK_TOKEN missing", file=sys.stderr)
    sys.exit(1)

CHANNEL = "#jimmy님의-morning-briefing"

d = json.load(open("/home/user/daily/briefing_data.json"))
date = d["date"]
cats = d["categories"]


def fmt_views(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}만회"
    return f"{n:,}회"


def clean_title(t: str) -> str:
    return html.unescape(t).strip().replace("\n", " ")


def link(text: str, url: str) -> str:
    # Slack mrkdwn link syntax: <url|text>
    safe = text.replace("|", "│").replace(">", "＞").replace("<", "＜")
    return f"<{url}|{safe}>"


order = ["A", "B", "C", "D", "E"]

# Pick highlight videos for Jimmy's 3 key points
a_top = cats["A"]["top"][0]
d_top = cats["D"]["top"][0]
b_top = next(
    (v for v in cats["B"]["top"] if "망가집니다" in v["title"] or "무조건" in v["title"]),
    cats["B"]["top"][0],
)

pattern_label = {
    "숫자형": "숫자 포함형",
    "질문형": "질문형",
    "비교형": "비교형",
    "공포긴박형": "공포·긴박형",
    "경험담형": "경험담형",
}

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

blocks = []

# ── ① Header
blocks.append({
    "type": "header",
    "text": {"type": "plain_text", "text": f"📅 {date} YouTube 트렌드 모닝 브리핑"},
})
blocks.append({
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": (
            "지난 *7일간* 한국 시청자가 가장 많이 본 *5개 카테고리*"
            "(은퇴·헬스·신앙·AI·독서) 상위 영상과 제목 패턴 정리"
        ),
    },
})
blocks.append({"type": "divider"})

# ── ② Category sections
for k in order:
    c = cats[k]
    lines = [f"*{c['tag']} 카테고리 {k} — {c['name']}*"]
    for i, v in enumerate(c["top"], 1):
        title = clean_title(v["title"])
        if len(title) > 70:
            title = title[:70] + "…"
        lines.append(
            f"{i}. {link(title, v['url'])}\n"
            f"   _{v['channel']}_ · {fmt_views(v['viewCount'])} · {v['publishedAt']}"
        )
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "\n".join(lines)[:2900]},
    })
    blocks.append({"type": "divider"})

# ── ③ Pattern analysis
pat_lines = ["*📊 카테고리별 제목 패턴 분석 (1위 패턴)*", ""]
for k in order:
    c = cats[k]
    p = c["pattern"]
    pat_lines.append(
        f"• *{k} {c['name']}* → `{pattern_label[p['winner']]}` "
        f"평균 *{fmt_views(p['winner_avg'])}*"
    )
pat_lines.append("")
pat_lines.append("*전체 패턴 평균 (참고):*")
pat_lines.append("```")
pat_lines.append(
    f"{'카테고리':<6}{'숫자형':>10}{'질문형':>10}{'비교형':>10}{'공포긴박':>10}{'경험담':>10}"
)
for k in order:
    avgs = cats[k]["pattern"]["avgs"]
    row = f"{k:<6}"
    for label in ["숫자형", "질문형", "비교형", "공포긴박형", "경험담형"]:
        v = avgs[label]["avg"]
        row += f"{(fmt_views(v) if v else '-'): >10}"
    pat_lines.append(row)
pat_lines.append("```")
blocks.append({
    "type": "section",
    "text": {"type": "mrkdwn", "text": "\n".join(pat_lines)},
})
blocks.append({"type": "divider"})

# ── ④ Jimmy's 3 key points
def trim(t, n=55):
    t = clean_title(t)
    return t[:n] + "…" if len(t) > n else t

p1 = (
    f"*포인트 1 · 💰 재무* — `공포·숫자 결합형` 제목이 폭발\n"
    f"📌 근거: {link(trim(a_top['title']), a_top['url'])} = *{fmt_views(a_top['viewCount'])}*\n"
    f"> 50대 남성은 _\"많이 받을수록 좋다\"_ 통념이 깨질 때 가장 강하게 반응. "
    f"건보료·세금 같은 *숨은 비용*을 수치로 보여주면 클릭률이 크게 상승.\n"
    f"🎯 *적용 아이디어*: \"IRP 10년 굴려봤더니 — 50대 개발자가 엑셀로 "
    f"시뮬레이션한 실수령액 (건보료까지 계산)\""
)
p2 = (
    f"*포인트 2 · 🤖 AI/개발* — `숫자+트렌드 정리형` 제목이 압도\n"
    f"📌 근거: {link(trim(d_top['title']), d_top['url'])} = *{fmt_views(d_top['viewCount'])}*\n"
    f"> Claude Code·Cursor 단일 도구 영상보다 _큐레이션 후속편_ 포맷이 "
    f"압도적 조회수. *20년차 개발자 + 50대 시니어* 관점은 희소한 권위.\n"
    f"🎯 *적용 아이디어*: \"20년차 개발자가 직접 써본 AI 코딩 도구 5종 — "
    f"50대에게 진짜 필요한 건 이거였다\""
)
p3 = (
    f"*포인트 3 · 💪 헬스* — `공포·긴박형` 조언 제목 우세\n"
    f"📌 근거: {link(trim(b_top['title']), b_top['url'])} = *{fmt_views(b_top['viewCount'])}*\n"
    f"> _\"걷기만으론 안 된다\"_ 처럼 *기존 습관을 흔드는* 메시지가 50대 남성에게 "
    f"가장 강하게 꽂힘. 헬스+신앙+개발 *멀티 정체성*은 신뢰도 가산점.\n"
    f"🎯 *적용 아이디어*: \"50대 개발자의 1년 헬스 일지 — QT처럼 매일 "
    f"기록했더니 인바디가 바뀌었습니다\""
)
blocks.append({
    "type": "section",
    "text": {"type": "mrkdwn", "text": "*💡 Jimmy님 채널 참고 핵심 포인트 3가지*"},
})
for p in [p1, p2, p3]:
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": p}})

blocks.append({"type": "divider"})
blocks.append({
    "type": "context",
    "elements": [{
        "type": "mrkdwn",
        "text": (
            f"_자동 생성 ({now_kst}) · YouTube Data API v3 · regionCode=KR · "
            f"publishedAfter=-7d · 총 25개 영상 분석_"
        ),
    }],
})

# Plain-text fallback (notification preview)
fallback = f"📅 {date} YouTube 트렌드 모닝 브리핑 — 5개 카테고리 25개 영상 분석"

payload = {
    "channel": CHANNEL,
    "text": fallback,
    "blocks": blocks,
    "unfurl_links": False,
    "unfurl_media": False,
}

req = urllib.request.Request(
    "https://slack.com/api/chat.postMessage",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    body = {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8')}"}

print(json.dumps(body, ensure_ascii=False, indent=2))
sys.exit(0 if body.get("ok") else 1)
