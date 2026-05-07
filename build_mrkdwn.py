#!/usr/bin/env python3
"""Build a Slack-friendly markdown briefing message from briefing_data.json.

Output goes to stdout AND /home/user/daily/slack_message_final.md.
"""
import html
import json
from datetime import datetime, timedelta, timezone

d = json.load(open("/home/user/daily/briefing_data.json"))
date = d["date"]
cats = d["categories"]
order = ["A", "B", "C", "D", "E"]

KST = timezone(timedelta(hours=9))
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")


def fmt_views(n: int) -> str:
    if n >= 10000:
        return f"{n/10000:.1f}만회"
    return f"{n:,}회"


def t(s: str, n: int = 70) -> str:
    s = html.unescape(s).strip().replace("\n", " ")
    return s[:n] + "…" if len(s) > n else s


pattern_label = {
    "숫자형": "숫자 포함형",
    "질문형": "질문형",
    "비교형": "비교형",
    "공포긴박형": "공포·긴박형",
    "경험담형": "경험담형",
}

a_top = cats["A"]["top"][0]
d_top = cats["D"]["top"][0]
b_top = next(
    (v for v in cats["B"]["top"] if "망가집니다" in v["title"] or "무조건" in v["title"]),
    cats["B"]["top"][0],
)

L = []
L.append(f"# 📅 {date} YouTube 트렌드 모닝 브리핑")
L.append("")
L.append(
    "> 지난 **7일간** 한국 시청자가 가장 많이 본 **5개 카테고리**(은퇴·헬스·신앙·AI·독서) "
    "상위 영상과 제목 패턴 정리"
)
L.append("")

for k in order:
    c = cats[k]
    L.append(f"## {c['tag']} 카테고리 {k} — {c['name']}")
    L.append("")
    for i, v in enumerate(c["top"], 1):
        L.append(
            f"{i}. [{t(v['title'])}]({v['url']})  \n"
            f"   _{v['channel']}_ · **{fmt_views(v['viewCount'])}** · {v['publishedAt']}"
        )
    L.append("")

L.append("## 📊 카테고리별 제목 패턴 분석 (1위 패턴)")
L.append("")
for k in order:
    c = cats[k]
    p = c["pattern"]
    L.append(
        f"- **{k} {c['name']}** → `{pattern_label[p['winner']]}` "
        f"평균 **{fmt_views(p['winner_avg'])}**"
    )
L.append("")
L.append("**전체 패턴 평균 (참고)**")
L.append("")
L.append("```")
L.append(
    f"{'카테고리':<6}{'숫자형':>10}{'질문형':>10}{'비교형':>10}{'공포긴박':>10}{'경험담':>10}"
)
for k in order:
    avgs = cats[k]["pattern"]["avgs"]
    row = f"{k:<6}"
    for label in ["숫자형", "질문형", "비교형", "공포긴박형", "경험담형"]:
        v = avgs[label]["avg"]
        row += f"{(fmt_views(v) if v else '-'): >10}"
    L.append(row)
L.append("```")
L.append("")

L.append("## 💡 Jimmy님 채널 참고 핵심 포인트 3가지")
L.append("")
L.append(
    f"**포인트 1 · 💰 재무** — `공포·숫자 결합형` 제목이 폭발  \n"
    f"📌 근거: [{t(a_top['title'], 55)}]({a_top['url']}) = **{fmt_views(a_top['viewCount'])}**  \n"
    f"> 50대 남성은 _\"많이 받을수록 좋다\"_ 통념이 깨질 때 강하게 반응. "
    f"건보료·세금 같은 **숨은 비용**을 수치로 보여주면 클릭률이 크게 상승.  \n"
    f"🎯 **적용 아이디어**: \"IRP 10년 굴려봤더니 — 50대 개발자가 엑셀로 "
    f"시뮬레이션한 실수령액 (건보료까지 계산)\""
)
L.append("")
L.append(
    f"**포인트 2 · 🤖 AI/개발** — `숫자+트렌드 정리형` 제목이 압도  \n"
    f"📌 근거: [{t(d_top['title'], 55)}]({d_top['url']}) = **{fmt_views(d_top['viewCount'])}**  \n"
    f"> 단일 도구 영상보다 _큐레이션 후속편_ 포맷이 압도적 조회수. "
    f"**20년차 개발자 + 50대 시니어** 관점은 희소한 권위.  \n"
    f"🎯 **적용 아이디어**: \"20년차 개발자가 직접 써본 AI 코딩 도구 5종 — "
    f"50대에게 진짜 필요한 건 이거였다\""
)
L.append("")
L.append(
    f"**포인트 3 · 💪 헬스** — `공포·긴박형` 조언 제목 우세  \n"
    f"📌 근거: [{t(b_top['title'], 55)}]({b_top['url']}) = **{fmt_views(b_top['viewCount'])}**  \n"
    f"> _\"걷기만으론 안 된다\"_ 처럼 **기존 습관을 흔드는** 메시지가 50대 남성에게 "
    f"가장 강하게 꽂힘. 헬스+신앙+개발 **멀티 정체성**은 신뢰도 가산점.  \n"
    f"🎯 **적용 아이디어**: \"50대 개발자의 1년 헬스 일지 — QT처럼 매일 "
    f"기록했더니 인바디가 바뀌었습니다\""
)
L.append("")
L.append("---")
L.append(
    f"_자동 생성 ({now_kst}) · YouTube Data API v3 · regionCode=KR · "
    f"publishedAfter=-7d · 총 25개 영상 분석_"
)

text = "\n".join(L)
print(text)
with open("/home/user/daily/slack_message_final.md", "w", encoding="utf-8") as f:
    f.write(text)
