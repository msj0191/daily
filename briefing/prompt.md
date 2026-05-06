# 매일 아침 WSJ·NYT 인기·논란 기사 브리핑

> 이 파일은 launchd → run-briefing.sh → `claude -p` 로 매일 아침 자동 실행됩니다.
> 본 작업은 **로컬 환경**(`CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE` 미설정)에서만 정상 동작합니다.
> Cloud Web 환경은 NYT/WSJ/Reddit/HN 호스트가 모두 차단되어 있어 사용 불가.

## 환경 변수

다음 변수가 셸에서 제공됩니다 (run-briefing.sh 가 .env 로딩):

- `NYT_API_KEY`   — NYT Most Popular + Article Search API
- `SLACK_TOKEN`   — Slack chat.postMessage Bot 토큰 (xoxb-)
- `SLACK_CHANNEL` — Slack 채널 ID (예: C0B13399JG3 = #wsj-nyt)
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` — (선택) Reddit OAuth

값이 빈 문자열이면 해당 단계는 건너뛰되, 최종 실행 요약에 사유를 명시.

## 작업 절차

### 1. NYT 수집

1-A. **Most Popular API**
- `https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json?api-key=$NYT_API_KEY`
- `https://api.nytimes.com/svc/mostpopular/v2/shared/1/facebook.json?api-key=$NYT_API_KEY`
- `https://api.nytimes.com/svc/mostpopular/v2/emailed/1.json?api-key=$NYT_API_KEY`
- 각 엔드포인트에서 상위 10개

1-B. **Article Search API** — 오늘 자 + Jimmy 관심 키워드 필터
- 엔드포인트: `https://api.nytimes.com/svc/search/v2/articlesearch.json`
- 키워드 OR 결합 (5개 그룹):
  - `"artificial intelligence" OR "Claude" OR "Anthropic"`
  - `"interest rate" OR "retirement" OR "pension"`
  - `"Israel" OR "Ukraine" OR "China trade"`
  - `"Christianity" OR "religion" OR "faith"`
  - `"cybersecurity" OR "vulnerability" OR "CVE"`
- 파라미터: `sort=newest`, `fq=section_name:("Technology" "Business" "Opinion" "World")`, `begin_date=YYYYMMDD` (오늘)

1-C. **RSS 보강** — 1-A·1-B 결과와 URL 기준 중복 제거
- `https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml`
- `https://rss.nytimes.com/services/xml/rss/nyt/Business.xml`
- `https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml`
- `https://rss.nytimes.com/services/xml/rss/nyt/World.xml`
- `https://rss.nytimes.com/services/xml/rss/nyt/Health.xml`

### 2. WSJ 수집 (RSS만, 본문 크롤링 금지)

- `https://feeds.a.dj.com/rss/RSSWorldNews.xml`
- `https://feeds.a.dj.com/rss/RSSWSJD.xml` (Tech)
- `https://feeds.a.dj.com/rss/RSSMarketsMain.xml`
- `https://feeds.a.dj.com/rss/RSSOpinion.xml`
- `https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml`

수집 항목: 제목, URL, description, pubDate. 오늘 자(pubDate)만 필터.
WSJ 페이월: 무료 가능 시 `🔓 무료`, 구독 필요 시 `🔒 구독` 태그. 본문 가져오지 않음.

### 3. Reddit·HN 교차 분석 (논란 지수)

3-A. Reddit (`oauth.reddit.com`) — 각 NYT 기사 제목 핵심 키워드로
`r/worldnews, r/technology, r/economics, r/investing, r/news, r/MachineLearning` 검색.
파라미터: `q=<키워드>&sort=hot&t=day&limit=5`. (REDDIT_CLIENT_ID 없으면 스킵)

3-B. HackerNews Algolia: `https://hn.algolia.com/api/v1/search?query=<키워드>&tags=story&numericFilters=created_at_i>{오늘 0시 UTC unix ts}`

3-C. 논란 지수 = `Reddit 댓글 × 0.4 + Reddit upvote × 0.3 + HN 댓글 × 0.3`. 매칭 안 되면 0. 상위 3개에 `🔥논란` 태그.

### 4. 최종 10개 선별

우선순위:
1. 논란 지수 높은 기사
2. NYT Most Popular 상위
3. Jimmy 관심 키워드 매칭 (AI·보안·재무·국제·신앙)

### 5. 출력 카드 (10개)

```
┌─────────────────────────────
│ 제목 (한국어 번역 병기)
│ 출처: NYT / WSJ  |  섹션명
│ 발행: KST 시각  |  접근: 🔓무료 / 🔒구독
│ 링크: <원문 URL>            ← 반드시 nytimes.com / wsj.com 도메인
│ 요약: AI 한국어 3줄
│ 반응: Reddit {up}↑ {com}💬 | HN {pt}pt {com}💬
│ 논란지수: {n점}  태그: {🔥논란 / 📈인기 / 💡인사이트}
│ Jimmy 관련도: {AI·보안·재무·신앙·국제 중 해당}
└─────────────────────────────
```

### 6. 오늘의 픽 2개

- **픽 A — 🔥 오늘의 논란**: 논란 지수 1위. 왜 논란인지 2문장 + Reddit 찬·반 의견 1개씩 + 원문 링크.
- **픽 B — 💡 Jimmy 추천**: 관심 키워드 + 실무 적용 가능성 (AI→Claude Code, 재무→은퇴 설계 등) + 원문 링크.

### 7. Slack 전송 (`#wsj-nyt`, channel_id=$SLACK_CHANNEL)

순서:
1. 📰 날짜 헤더: `YYYY년 MM월 DD일 | WSJ·NYT 브리핑`
2. 💡 픽 B (Jimmy 추천) — 최상단
3. 🔥 픽 A (논란)
4. 📋 전체 10개 (NYT/WSJ 섹션 구분)
5. 📊 실행 요약:

```
================================
📊 WSJ·NYT 브리핑 실행 완료
================================
실행 시각      : {KST}
NYT API 호출   : {n}회
WSJ RSS 수집   : {n}개 피드
Reddit 교차    : {n}개 매칭
HN 교차        : {n}개 매칭
최종 선별      : 10개
Slack 전송     : ✅ {링크} / ❌ {오류}
================================
```

## 금지 사항

- 행동 가정 문장(`"전송하겠습니다"` 등)을 API 호출 전 출력 금지
- WSJ·NYT 본문 크롤링·저장 금지 (RSS 요약만)
- 기사 원문 전문을 Slack에 붙여넣기 금지 (3줄 요약만)
- API 키·토큰을 로그·메시지에 노출 금지
- NYT API 호출 한도 초과 금지 (500/day, 10/min)
- Reddit 미인증 호출 금지 (60/min)
- 페이월 본문 무단 접근 금지
- **링크 도메인은 반드시 `nytimes.com` 또는 `wsj.com`** — 제3매체 인용 링크 사용 금지

## 종료 조건

- Slack 메시지 전송 성공 시 정상 종료
- 실패 시 `logs/$(date +%F).log` 에 오류 기록 + 종료 코드 1
