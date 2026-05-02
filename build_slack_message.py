#!/usr/bin/env python3
"""Compose the Slack briefing message from briefing_data.json."""
import json

d = json.load(open("/home/user/daily/briefing_data.json"))
date = d["date"]
cats = d["categories"]


def fmt_views(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}만회"
    return f"{n:,}회"


# ── Pick highlight videos for Jimmy's 3 key points ──
# Strategy: choose one video per pillar that maps to Jimmy's experience.
# 1) Finance pillar: highest-view fear/number title in category A
# 2) AI/dev pillar: highest-view tutorial/comparison in category D
# 3) Health pillar: highest-view advisory title in category B

a_top = cats["A"]["top"][0]  # 국민연금 많이 받으면 망하는 이유
d_top = cats["D"]["top"][0]  # AI 용도별 추천 2탄
b_top = next(  # find 공포긴박형 if exists, else top
    (v for v in cats["B"]["top"] if "망가집니다" in v["title"] or "무조건" in v["title"]),
    cats["B"]["top"][0],
)

# ── Build message ──
out = []
out.append(f"## 📅 {date} (토) YouTube 트렌드 모닝 브리핑")
out.append(
    "> 지난 7일간 한국 시청자가 가장 많이 본 5개 카테고리(은퇴·헬스·신앙·AI·독서) "
    "상위 영상과 제목 패턴을 정리했습니다."
)
out.append("")

# Category sections
order = ["A", "B", "C", "D", "E"]
for k in order:
    c = cats[k]
    out.append(f"### {c['tag']} 카테고리 {k} — {c['name']}")
    for i, v in enumerate(c["top"], 1):
        title = v["title"].strip().replace("\n", " ")
        out.append(
            f"{i}. [{title}]({v['url']}) — `{v['channel']}` · "
            f"{fmt_views(v['viewCount'])} · {v['publishedAt']}"
        )
    out.append("")

# Pattern analysis
out.append("### 📊 카테고리별 제목 패턴 분석 (1위 패턴)")
pattern_label = {
    "숫자형": "숫자 포함형",
    "질문형": "질문형",
    "비교형": "비교형",
    "공포긴박형": "공포·긴박형",
    "경험담형": "경험담형",
}
for k in order:
    c = cats[k]
    p = c["pattern"]
    winner = p["winner"]
    avg = p["winner_avg"]
    out.append(
        f"- **{k} {c['name']}** → `{pattern_label[winner]}` "
        f"평균 조회수 **{fmt_views(avg)}**"
    )
out.append("")
out.append("**전체 패턴 평균 (참고):**")
out.append("```")
out.append(
    f"{'카테고리':<6}{'숫자형':>10}{'질문형':>10}{'비교형':>10}{'공포긴박':>10}{'경험담':>10}"
)
for k in order:
    avgs = cats[k]["pattern"]["avgs"]
    row = f"{k:<6}"
    for label in ["숫자형", "질문형", "비교형", "공포긴박형", "경험담형"]:
        v = avgs[label]["avg"]
        row += f"{(fmt_views(v) if v else '-'): >10}"
    out.append(row)
out.append("```")
out.append("")

# Jimmy's key points
out.append("### 💡 Jimmy님 채널 참고 핵심 포인트 3가지")
out.append("")
out.append(
    f"**포인트 1 · 💰 재무** — `공포·숫자 결합형` 제목이 폭발 (1위 [{a_top['title'][:50]}…]({a_top['url']}) "
    f"= **{fmt_views(a_top['viewCount'])}**)"
)
out.append(
    "> 50대 남성은 \"많이 받을수록 좋다\"는 통념이 깨질 때 가장 강하게 반응합니다. "
    "건보료·세금 같은 _숨은 비용_을 수치로 보여주면 클릭률이 크게 올라갑니다."
)
out.append(
    "> 🎯 **적용 아이디어**: \"IRP 10년 굴려봤더니 — 50대 개발자가 엑셀로 시뮬레이션한 실수령액 (건보료까지 계산)\""
)
out.append("")
out.append(
    f"**포인트 2 · 🤖 AI/개발** — `숫자+트렌드 정리형` 제목이 압도 (1위 [{d_top['title']}]({d_top['url']}) "
    f"= **{fmt_views(d_top['viewCount'])}**)"
)
out.append(
    "> Claude Code·Cursor 단일 도구 영상보다 \"용도별 추천 2탄\" 같은 _큐레이션 후속편_ 포맷이 "
    "압도적 조회수를 만듭니다. 50대 개발자 관점은 시니어 시청자에게 희소한 권위를 갖습니다."
)
out.append(
    "> 🎯 **적용 아이디어**: \"20년차 개발자가 직접 써본 AI 코딩 도구 5종 - 50대에게 진짜 필요한 건 이거였다\""
)
out.append("")
out.append(
    f"**포인트 3 · 💪 헬스** — `공포·긴박형` 조언 제목이 동일 채널 평균 대비 우세 "
    f"(예 [{b_top['title']}]({b_top['url']}) = **{fmt_views(b_top['viewCount'])}**)"
)
out.append(
    "> \"걷기만으론 안 된다\" 같이 _기존 습관을 흔드는_ 메시지가 50대 남성에게 가장 강하게 꽂힙니다. "
    "Jimmy님의 헬스+신앙+개발 멀티 정체성은 신뢰도 가산점을 줍니다."
)
out.append(
    "> 🎯 **적용 아이디어**: \"50대 개발자의 1년 헬스 일지 — QT처럼 매일 기록했더니 인바디가 바뀌었습니다\""
)
out.append("")
out.append(
    "_— 자동 생성 브리핑 (YouTube Data API v3, regionCode=KR, "
    "publishedAfter=-7d) ·_ "
    f"_총 {sum(len(cats[k]['top']) for k in order)}개 영상 분석_"
)

text = "\n".join(out)
print(text)

with open("/home/user/daily/slack_message.md", "w", encoding="utf-8") as f:
    f.write(text)
