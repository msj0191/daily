#!/usr/bin/env python3
"""YouTube morning briefing aggregator.

Performs 1 search.list call per category (5 total) plus a single videos.list
batch call to fetch statistics for all candidate videos.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    print("ERROR: YOUTUBE_API_KEY missing", file=sys.stderr)
    sys.exit(1)

published_after = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

CATEGORIES = {
    "A": {
        "name": "은퇴·재무 설계",
        "tag": "💰재무인사이트",
        "lang": "ko",
        "keywords": [
            "50대 은퇴 준비",
            "퇴직연금 수령 방법",
            "개인연금 IRP 전략",
            "노후 자산 관리",
            "조기 은퇴 FIRE",
        ],
        "query": "은퇴 연금",
        "filter_terms": [
            "은퇴", "연금", "irp", "노후", "퇴직", "fire", "재테크",
            "isa", "자산", "세액공제", "국민연금", "건보료",
        ],
    },
    "B": {
        "name": "건강·헬스",
        "tag": "💪헬스루틴",
        "lang": "ko",
        "keywords": [
            "50대 헬스 루틴",
            "중년 남성 근력 운동",
            "헬스장 프로그램 50대",
            "인바디 체지방 감량",
            "간헐적 단식 50대",
        ],
        "query": "50대 헬스",
        "filter_terms": [
            "50대", "중년", "헬스", "근력", "체지방", "단식",
            "인바디", "오십", "다이어트", "운동", "오운완", "턱걸이",
        ],
    },
    "C": {
        "name": "신앙·성경 연구",
        "tag": "📖신앙성장",
        "lang": "ko",
        "keywords": [
            "성경 QT 방법",
            "창세기 강해",
            "성경 인문학",
            "기독교 독서 추천",
            "어린이 사역 교육",
        ],
        "query": "성경 QT",
        "filter_terms": [
            "qt", "큐티", "성경", "창세기", "강해", "기독교",
            "사역", "말씀", "묵상", "필사", "목사", "교회",
        ],
    },
    "D": {
        "name": "AI·개발 도구 트렌드",
        "tag": "🤖AI실무",
        "lang": "ko",
        "keywords": [
            "claude code 사용법",
            "AI 코딩 도구 비교",
            "cursor vs copilot",
            "MCP 서버 활용",
            "LLM 로컬 실행",
        ],
        "query": "claude code AI",
        "filter_terms": [
            "claude", "cursor", "copilot", "mcp", "llm", "ai",
            "코딩", "개발", "코드", "agent", "vibe", "gpt", "gemini",
        ],
    },
    "E": {
        "name": "독서·자기계발",
        "tag": "📚지식확장",
        "lang": "ko",
        "keywords": [
            "50대 추천 도서",
            "독서 모임 운영 방법",
            "비즈니스 책 리뷰",
            "인문학 강의",
            "지식 관리 시스템",
        ],
        "query": "독서 추천",
        "filter_terms": [
            "도서", "독서", "책", "북튜버", "인문학", "지식",
            "책추천", "책리뷰", "자기계발", "리뷰", "교양",
        ],
    },
}


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_category(cat_key: str, cfg: dict) -> list:
    # Single API call per category, using the pre-built distinctive-token query.
    params = {
        "key": API_KEY,
        "part": "snippet",
        "q": cfg["query"],
        "type": "video",
        "order": "viewCount",
        "publishedAfter": published_after,
        "regionCode": "KR",
        "relevanceLanguage": cfg["lang"],
        "maxResults": 25,
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(
        params
    )
    data = http_get(url)
    items = []
    for it in data.get("items", []):
        vid = it.get("id", {}).get("videoId")
        if not vid:
            continue
        sn = it["snippet"]
        items.append(
            {
                "videoId": vid,
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "publishedAt": sn.get("publishedAt", ""),
                "description": sn.get("description", ""),
            }
        )
    return items


def fetch_stats(video_ids: list) -> dict:
    if not video_ids:
        return {}
    out = {}
    # videos.list supports up to 50 IDs per call.
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        params = {
            "key": API_KEY,
            "part": "statistics,contentDetails",
            "id": ",".join(batch),
        }
        url = (
            "https://www.googleapis.com/youtube/v3/videos?"
            + urllib.parse.urlencode(params)
        )
        data = http_get(url)
        for it in data.get("items", []):
            stats = it.get("statistics", {})
            out[it["id"]] = {
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": int(stats.get("likeCount", 0)),
                "commentCount": int(stats.get("commentCount", 0)),
            }
    return out


# ── Pattern detection ─────────────────────────────────────────
import re

NUM_RE = re.compile(r"\d+")
QUESTION_MARKERS = ("?", "?", "왜 ", "어떻게", "무엇", "뭐가", "뭐죠", "할까", "일까")
COMPARE_MARKERS = (" vs ", "VS", "vs.", "대결", "비교", "차이")
FEAR_MARKERS = (
    "후회",
    "실수",
    "조심",
    "위험",
    "절대",
    "모르면",
    "큰일",
    "망함",
    "주의",
    "경고",
    "충격",
)
EXPERIENCE_MARKERS = (
    "해봤",
    "후기",
    "경험",
    "직접",
    "리얼",
    "솔직",
    "실제",
    "도전",
    "체험",
    "정리",
)


def classify(title: str) -> list:
    labels = []
    if NUM_RE.search(title):
        labels.append("숫자형")
    if any(m in title for m in QUESTION_MARKERS):
        labels.append("질문형")
    if any(m.lower() in title.lower() for m in COMPARE_MARKERS):
        labels.append("비교형")
    if any(m in title for m in FEAR_MARKERS):
        labels.append("공포긴박형")
    if any(m in title for m in EXPERIENCE_MARKERS):
        labels.append("경험담형")
    return labels


def analyze_patterns(videos: list) -> dict:
    buckets = {
        "숫자형": [],
        "질문형": [],
        "비교형": [],
        "공포긴박형": [],
        "경험담형": [],
    }
    for v in videos:
        for lbl in classify(v["title"]):
            buckets[lbl].append(v["viewCount"])
    avgs = {}
    for k, lst in buckets.items():
        if lst:
            avgs[k] = {"count": len(lst), "avg": sum(lst) // len(lst)}
        else:
            avgs[k] = {"count": 0, "avg": 0}
    winner = max(avgs.items(), key=lambda kv: kv[1]["avg"])
    return {"avgs": avgs, "winner": winner[0], "winner_avg": winner[1]["avg"]}


def one_line_summary(title: str, description: str) -> str:
    # Heuristic summary from title + leading description.
    desc = (description or "").strip().replace("\n", " ")
    if len(desc) > 90:
        desc = desc[:90] + "…"
    if not desc:
        return title
    return desc


# ── Run ────────────────────────────────────────────────────────
result = {}
all_video_ids = []
for key, cfg in CATEGORIES.items():
    print(f"[search] Category {key}: {cfg['name']}", file=sys.stderr)
    items = search_category(key, cfg)
    result[key] = {"cfg": cfg, "items": items}
    all_video_ids.extend([x["videoId"] for x in items])

print(f"[stats] fetching {len(all_video_ids)} video stats", file=sys.stderr)
stats = fetch_stats(all_video_ids)

# Attach stats and pick top 5 per category.
output = {"date": datetime.now().strftime("%Y-%m-%d"), "categories": {}}
for key, payload in result.items():
    enriched = []
    filter_terms = [t.lower() for t in payload["cfg"].get("filter_terms", [])]
    for v in payload["items"]:
        s = stats.get(v["videoId"], {})
        v["viewCount"] = s.get("viewCount", 0)
        v["likeCount"] = s.get("likeCount", 0)
        # Keep only videos whose title or description mentions a filter term —
        # screens out viral noise that matched a single token coincidentally.
        haystack = (v["title"] + " " + v["description"]).lower()
        if filter_terms and not any(t in haystack for t in filter_terms):
            continue
        enriched.append(v)
    enriched.sort(key=lambda x: x["viewCount"], reverse=True)
    top = enriched[:5]
    pattern = analyze_patterns(enriched)  # use full pool for pattern stats
    output["categories"][key] = {
        "name": payload["cfg"]["name"],
        "tag": payload["cfg"]["tag"],
        "top": [
            {
                "title": v["title"],
                "channel": v["channel"],
                "viewCount": v["viewCount"],
                "publishedAt": v["publishedAt"][:10],
                "url": f"https://www.youtube.com/watch?v={v['videoId']}",
                "summary": one_line_summary(v["title"], v["description"]),
            }
            for v in top
        ],
        "pattern": pattern,
    }

with open("/home/user/daily/briefing_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("Done. Saved to briefing_data.json", file=sys.stderr)
