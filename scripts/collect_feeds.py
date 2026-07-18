#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뉴스 피드 수집 릴레이 (GitHub Actions 전용) — scripts/collect_feeds.py

목적
  Claude 예약 루틴의 샌드박스는 egress 정책상 뉴스 호스트에 접근할 수 없다(403 host_not_allowed).
  이 스크립트는 네트워크가 자유로운 GitHub Actions 러너에서 실행되어, 키가 필요 없는
  공개 RSS/API만으로 기사 메타데이터(제목·링크·짧은 발췌)를 수집해
  data/latest.json 스냅샷으로 저장한다. Claude 루틴은 raw.githubusercontent.com에서
  이 파일만 읽는다.

자격증명
  불필요. 전 소스가 키리스 공개 피드이며, 커밋은 워크플로의 GITHUB_TOKEN이 처리한다.

실패 정책
  - 개별 소스 실패는 source_status에 기록하고 계속 진행 (부분 실패 허용)
  - 모든 소스 실패 시에만 exit 1 → 워크플로 실패 → GitHub 이메일 알림
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) feed-relay/1.0 (personal daily briefing)"}
TIMEOUT = 20
PER_SOURCE_CAP = 15      # 소스당 최대 기사 수
SUMMARY_MAX = 300        # 발췌 최대 길이(자) — 전문 복제 방지

# 키리스 공개 RSS 피드 (URL이 바뀌면 source_status에 실패로 표기되어 즉시 발견됨)
RSS_FEEDS = {
    "NYT-World":        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "NYT-Technology":   "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "NYT-Business":     "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "WSJ-World":        "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "WSJ-Tech":         "https://feeds.content.dowjones.io/public/rss/RSSWSJD",
    "WSJ-Markets":      "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    # Reddit은 클라우드 IP를 간헐 차단하므로 best-effort 소스로 취급
    "Reddit-technology": "https://www.reddit.com/r/technology/top/.rss?t=day",
    "Reddit-programming": "https://www.reddit.com/r/programming/top/.rss?t=day",
}
HN_API = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=20"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(s: str | None) -> str:
    """HTML 태그 제거·엔티티 복원·공백 정리 후 SUMMARY_MAX 자로 절단."""
    s = html.unescape(_TAG_RE.sub(" ", s or ""))
    return _WS_RE.sub(" ", s).strip()[:SUMMARY_MAX]


def iso_from_struct(t) -> str | None:
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        return None


def fetch_rss(name: str, url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"RSS 파싱 실패: {parsed.bozo_exception}")
    items = []
    for e in parsed.entries[:PER_SOURCE_CAP]:
        title = clean_text(e.get("title"))
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        items.append({
            "source": name,
            "title": title,
            "url": link,
            "summary": clean_text(e.get("summary") or e.get("description")),
            "published_utc": iso_from_struct(e.get("published_parsed") or e.get("updated_parsed")),
        })
    return items


def fetch_hn() -> list[dict]:
    r = requests.get(HN_API, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", [])[:PER_SOURCE_CAP]:
        title = clean_text(h.get("title"))
        if not title:
            continue
        hn_link = f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        items.append({
            "source": "HackerNews",
            "title": title,
            "url": h.get("url") or hn_link,
            "summary": f"HN {h.get('points', 0)}점 · 댓글 {h.get('num_comments', 0)}개 · {hn_link}",
            "published_utc": h.get("created_at"),
        })
    return items


def main() -> int:
    all_items: list[dict] = []
    status: dict[str, dict] = {}

    jobs = [("HackerNews", fetch_hn)]
    jobs += [(n, (lambda n=n, u=u: fetch_rss(n, u))) for n, u in RSS_FEEDS.items()]

    for name, fn in jobs:
        try:
            got = fn()
            status[name] = {"ok": True, "count": len(got)}
            all_items.extend(got)
        except Exception as exc:  # 개별 소스 실패는 기록 후 계속
            status[name] = {"ok": False, "error": str(exc)[:200]}

    # URL 기준 중복 제거 (추적 파라미터 제거 후 비교)
    seen: set[str] = set()
    deduped: list[dict] = []
    for it in all_items:
        key = it["url"].split("?utm", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    deduped.sort(key=lambda x: x.get("published_utc") or "", reverse=True)

    now_utc = datetime.now(timezone.utc)
    out = {
        "generated_at_utc": now_utc.isoformat(timespec="seconds"),
        "generated_at_kst": now_utc.astimezone(KST).isoformat(timespec="seconds"),
        "source_status": status,
        "total_items": len(deduped),
        "items": deduped,
    }

    Path("data").mkdir(exist_ok=True)
    payload = json.dumps(out, ensure_ascii=False, indent=1)
    Path("data/latest.json").write_text(payload, encoding="utf-8")
    archive = Path("data/archive")
    archive.mkdir(parents=True, exist_ok=True)
    (archive / f"{now_utc.astimezone(KST):%Y-%m-%d}.json").write_text(payload, encoding="utf-8")

    ok = sum(1 for s in status.values() if s["ok"])
    print(f"수집 완료: 소스 {ok}/{len(status)} 성공, 총 {len(deduped)}건")
    for n, s in status.items():
        print(f"  - {n}: {'OK ' + str(s['count']) + '건' if s['ok'] else 'FAIL ' + s['error']}")

    if ok == 0:
        print("모든 소스 실패 — 워크플로를 실패 처리하여 GitHub 알림을 유발합니다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
