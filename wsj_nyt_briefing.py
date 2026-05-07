#!/usr/bin/env python3
"""WSJ·NYT daily briefing collector.

Pulls NYT Most Popular (3 endpoints), NYT Article Search filtered by
Jimmy's interest keywords, NYT/WSJ section RSS feeds, and cross-checks
each article against HackerNews and Reddit for reaction metrics.

Output: data/briefing/wsj-nyt-YYYY-MM-DD.json
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

NYT_API_KEY = os.environ.get("NYT_API_KEY")
if not NYT_API_KEY:
    print("ERROR: NYT_API_KEY missing", file=sys.stderr)
    sys.exit(1)

UA = "msj0191-daily/1.0 (+https://github.com/msj0191/daily)"
TIMEOUT = 30
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).date()
TODAY_STR = TODAY.strftime("%Y-%m-%d")

INTERESTS = [
    ("artificial intelligence", "AI"),
    ("Claude", "AI"),
    ("Anthropic", "AI"),
    ("OpenAI", "AI"),
    ("interest rate", "재무"),
    ("retirement", "재무"),
    ("pension", "재무"),
    ("Israel", "국제"),
    ("Ukraine", "국제"),
    ("China trade", "국제"),
    ("Christianity", "신앙"),
    ("religion", "신앙"),
    ("faith", "신앙"),
    ("cybersecurity", "보안"),
    ("vulnerability", "보안"),
    ("CVE", "보안"),
]


def http_get(url: str, headers: dict | None = None) -> bytes:
    h = {"User-Agent": UA, "Accept": "application/json,text/xml,*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def get_json(url: str) -> dict:
    return json.loads(http_get(url).decode("utf-8"))


def get_text(url: str) -> str:
    return http_get(url).decode("utf-8", errors="replace")


def normalize_url(url: str) -> str:
    if not url:
        return ""
    u = url.split("?")[0].split("#")[0].rstrip("/").lower()
    # Drop scheme to bridge http vs https variants
    return re.sub(r"^https?://", "", u)


# ── NYT Most Popular ────────────────────────────────────────────────
def nyt_most_popular() -> list:
    out = []
    endpoints = [
        ("viewed", "viewed/1.json"),
        ("shared_fb", "shared/1/facebook.json"),
        ("emailed", "emailed/1.json"),
    ]
    for kind, path in endpoints:
        try:
            url = (
                f"https://api.nytimes.com/svc/mostpopular/v2/{path}"
                f"?api-key={NYT_API_KEY}"
            )
            data = get_json(url)
            for a in data.get("results", [])[:10]:
                out.append({
                    "source": "NYT",
                    "rank_kind": kind,
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "section": a.get("section", ""),
                    "abstract": a.get("abstract", ""),
                    "byline": a.get("byline", ""),
                    "published_date": a.get("published_date", ""),
                    "access": "free",
                })
            time.sleep(7)  # NYT limit: 10 req/min
        except Exception as e:
            print(f"[err] NYT MostPopular {kind}: {e}", file=sys.stderr)
    return out


# ── NYT Article Search (interest keyword filter) ────────────────────
def nyt_article_search() -> list:
    out = []
    today_yyyymmdd = TODAY.strftime("%Y%m%d")
    queries = sorted({k for k, _ in INTERESTS})
    q = " OR ".join(f'"{k}"' for k in queries[:10])
    fq = 'section_name:("Technology" "Business" "Opinion" "World")'
    params = {
        "q": q,
        "fq": fq,
        "sort": "newest",
        "begin_date": today_yyyymmdd,
        "api-key": NYT_API_KEY,
    }
    url = (
        "https://api.nytimes.com/svc/search/v2/articlesearch.json?"
        + urllib.parse.urlencode(params)
    )
    try:
        data = get_json(url)
        docs = data.get("response", {}).get("docs", [])
        for d in docs[:10]:
            out.append({
                "source": "NYT",
                "rank_kind": "article_search",
                "title": ((d.get("headline") or {}).get("main") or "").strip(),
                "url": d.get("web_url", ""),
                "section": d.get("section_name", ""),
                "abstract": (d.get("abstract") or d.get("snippet") or "").strip(),
                "byline": (d.get("byline") or {}).get("original", "") or "",
                "published_date": d.get("pub_date", ""),
                "access": "free",
            })
        time.sleep(7)
    except Exception as e:
        print(f"[err] NYT ArticleSearch: {e}", file=sys.stderr)
    return out


# ── RSS parser ──────────────────────────────────────────────────────
def parse_rss(xml_text: str) -> list:
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"[warn] RSS parse error: {e}", file=sys.stderr)
        return out
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        # strip HTML from description
        desc = re.sub(r"<[^>]+>", "", desc)
        pub = (item.findtext("pubDate") or "").strip()
        out.append({
            "title": title,
            "url": link,
            "abstract": desc,
            "published_date": pub,
        })
    return out


def fetch_rss_set(feeds: list, source: str, default_access: str) -> list:
    out = []
    for section, url in feeds:
        try:
            xml = get_text(url)
            for item in parse_rss(xml):
                item["source"] = source
                item["section"] = section
                item["rank_kind"] = "rss"
                item["byline"] = ""
                item["access"] = default_access
                out.append(item)
        except Exception as e:
            print(f"[err] {source} RSS {section}: {e}", file=sys.stderr)
    return out


def nyt_rss() -> list:
    feeds = [
        ("Technology", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
        ("Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
        ("Opinion", "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml"),
        ("World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("Health", "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml"),
    ]
    return fetch_rss_set(feeds, "NYT", "free")


def wsj_rss() -> list:
    feeds = [
        ("World", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
        ("Tech", "https://feeds.a.dj.com/rss/RSSWSJD.xml"),
        ("Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
        ("Opinion", "https://feeds.a.dj.com/rss/RSSOpinion.xml"),
        ("Business", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"),
    ]
    return fetch_rss_set(feeds, "WSJ", "paywall")


# ── HN cross-check ──────────────────────────────────────────────────
def hn_search(keywords: list) -> dict:
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=36)).timestamp())
    matches: dict = {}
    for kw in keywords:
        try:
            url = (
                "https://hn.algolia.com/api/v1/search?"
                + urllib.parse.urlencode({
                    "query": kw,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff}",
                    "hitsPerPage": 10,
                })
            )
            data = get_json(url)
            for hit in data.get("hits", []):
                u = hit.get("url") or ""
                if not u:
                    continue
                key = normalize_url(u)
                pts = hit.get("points") or 0
                comm = hit.get("num_comments") or 0
                cur = matches.get(key)
                if cur is None or (pts + comm) > (cur["points"] + cur["comments"]):
                    matches[key] = {
                        "points": pts,
                        "comments": comm,
                        "hn_url": (
                            "https://news.ycombinator.com/item?id="
                            + str(hit.get("objectID", ""))
                        ),
                    }
        except Exception as e:
            print(f"[warn] HN '{kw}': {e}", file=sys.stderr)
    return matches


# ── Reddit cross-check (public endpoint, gentle rate) ───────────────
def reddit_search(keywords: list) -> dict:
    matches: dict = {}
    subs = ["worldnews", "technology", "economics", "news"]
    for kw in keywords:
        for sub in subs:
            try:
                url = (
                    f"https://www.reddit.com/r/{sub}/search.json?"
                    + urllib.parse.urlencode({
                        "q": kw,
                        "sort": "hot",
                        "t": "day",
                        "limit": 5,
                        "restrict_sr": "on",
                    })
                )
                data = get_json(url)
                for child in data.get("data", {}).get("children", []):
                    p = child.get("data", {})
                    u = p.get("url_overridden_by_dest") or p.get("url", "")
                    if not u:
                        continue
                    key = normalize_url(u)
                    ups = p.get("ups") or 0
                    comm = p.get("num_comments") or 0
                    cur = matches.get(key)
                    if cur is None or (ups + comm) > (
                        cur["upvotes"] + cur["comments"]
                    ):
                        matches[key] = {
                            "upvotes": ups,
                            "comments": comm,
                            "reddit_url": (
                                "https://www.reddit.com" + p.get("permalink", "")
                            ),
                        }
                time.sleep(1.5)  # gentle on 60 req/min unauth limit
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"[warn] Reddit rate-limited; sleeping 30s", file=sys.stderr)
                    time.sleep(30)
                else:
                    print(f"[warn] Reddit /r/{sub} '{kw}': {e}", file=sys.stderr)
            except Exception as e:
                print(f"[warn] Reddit /r/{sub} '{kw}': {e}", file=sys.stderr)
    return matches


# ── Aggregate / score ───────────────────────────────────────────────
def deduplicate(articles: list) -> list:
    seen: dict = {}
    for a in articles:
        key = normalize_url(a.get("url", ""))
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            a["rank_kinds"] = [a["rank_kind"]]
            seen[key] = a
            continue
        kinds = set(existing.get("rank_kinds", []))
        kinds.add(a["rank_kind"])
        existing["rank_kinds"] = sorted(kinds)
        # Prefer the entry with longer abstract
        if len(a.get("abstract", "")) > len(existing.get("abstract", "")):
            existing["abstract"] = a["abstract"]
    return list(seen.values())


def tag_interests(article: dict) -> list:
    text = (article.get("title", "") + " " + article.get("abstract", "")).lower()
    tags = set()
    for kw, group in INTERESTS:
        if kw.lower() in text:
            tags.add(group)
    return sorted(tags)


def main():
    print(f"[info] Briefing date: {TODAY_STR} KST", file=sys.stderr)
    articles: list = []
    print("[info] NYT Most Popular...", file=sys.stderr)
    articles += nyt_most_popular()
    print("[info] NYT Article Search...", file=sys.stderr)
    articles += nyt_article_search()
    print("[info] NYT RSS...", file=sys.stderr)
    articles += nyt_rss()
    print("[info] WSJ RSS...", file=sys.stderr)
    articles += wsj_rss()

    articles = deduplicate(articles)
    print(f"[info] {len(articles)} unique articles", file=sys.stderr)

    # Build keyword set: explicit interests + 3-word slugs from top NYT titles
    keywords: set = {kw for kw, _ in INTERESTS}
    for a in articles[:25]:
        words = re.findall(r"[A-Za-z]{3,}", a.get("title", ""))
        if len(words) >= 2:
            keywords.add(" ".join(words[:3]))

    print(f"[info] HN cross-check ({len(keywords)} keywords)...", file=sys.stderr)
    hn = hn_search(sorted(keywords))
    print(f"[info] Reddit cross-check...", file=sys.stderr)
    reddit = reddit_search(sorted(keywords))

    for a in articles:
        key = normalize_url(a.get("url", ""))
        h = hn.get(key, {})
        r = reddit.get(key, {})
        a["hn"] = h
        a["reddit"] = r
        score = (
            (r.get("comments", 0) * 0.4)
            + (r.get("upvotes", 0) * 0.3)
            + (h.get("comments", 0) * 0.3)
        )
        a["controversy_score"] = round(score, 2)
        a["interest_tags"] = tag_interests(a)

    articles.sort(key=lambda a: a["controversy_score"], reverse=True)

    out = {
        "generated_at": datetime.now(KST).isoformat(),
        "date": TODAY_STR,
        "total": len(articles),
        "articles": articles,
    }

    out_dir = "data/briefing"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/wsj-nyt-{TODAY_STR}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[done] {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
