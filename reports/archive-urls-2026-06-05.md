# 시드 1차 배치 28건 — archive_url 보강 리포트

> 2026-06-05 산출. 근거: docs/05 리스크 표(출처 소실 대비 web.archive.org 의무화).
> 대상: `git ls-files`로 커밋된 시드 후보 28개 파일(오늘 추가된 미커밋 후보 23건은 제외).
> 방식: 각 URL을 `archive.org/wayback/available`(+ CDX) 조회 → 기존 스냅샷 있으면 채택, 없으면 `web.archive.org/save`로 신규 저장 후 재조회.

## 요약

- **대상 출처 URL: 54건** (incident/new_marker의 `source_url` 9건 + new_term evidence의 `url` 45건).
- **archive_url 확보: 53건 / 54건 (98%)**. 미확보 1건(아래 실패 목록).
- 스키마: `candidate-term.schema.json`의 `evidence` 항목에 `archive_url` 필드가 정식 정의되어 있음(line 60, "web.archive.org 백업 — 위키/뉴스는 필수 권장"). `additionalProperties` 제한 없음. incident/new_marker payload에는 `archive_url` 필드가 명시 정의돼 있지는 않으나 `additionalProperties: false`가 아니므로 `source_url` 옆에 형제 필드로 추가해도 스키마 통과 확인.
- **검증: `uv run python scripts/validate_candidates.py` → 28 통과 / 0 실패** (보강 후).

### 적용 내역(파일 변경 26건)

| 분류 | 건수 | 설명 |
|---|---|---|
| 기존 실(real) archive_url 유지 | 7 | 이전 배치에서 이미 정상 타임스탬프 보유 → 미변경 |
| 플레이스홀더(`/web/2024/`) → 실 스냅샷 교체 | 14 | `web/2024/`는 실제 캡처가 아닌 리다이렉트 URL이라 정식 타임스탬프로 교체 |
| evidence에 신규 추가(기존 없음) | 23 | |
| incident/new_marker `source_url`에 형제 `archive_url` 신규 추가 | 9 | |
| 미확보(실패) | 1 | newstomato.com — 캡처 없음·저장 실패 |

> 미변경 2개 파일: `new_term--hannam.json`(이미 실 archive_url 2건 보유), `new_term--seunsangnim.json`(유일 출처가 미아카이브).

### namu.wiki / 커뮤니티 URL 플래그

- **없음.** 28개 파일의 54개 출처 URL 중 `namu.wiki`/`namuwiki` 도메인 0건, `source_type=community` 0건.
- 참고: `femiwiki.com`(페미위키)은 `source_type=wiki`(CC BY-SA)로 분류된 위키이며 namu.wiki·커뮤니티 게시판이 아니므로 아카이브 대상에 포함(플래그 비대상).

### 방식별 분포(매핑 행 53건 기준)

- 기존 스냅샷(available 조회): 35
- 기존 스냅샷(CDX 조회): 2
- 기존(이전 배치에서 이미 보유, 미변경): 7
- 신규 저장(`save`로 당일 캡처 생성): 7행 — 고유 URL 6개(kci는 hongeo·jeolladian 2파일에서 공유): renault(hankookilbo), jipge(wikipedia), karnews, kci, nate(jwajom), khan(nomu)
- URL 정규화로 회수: 2 — no-ala(mt.co.kr→news.mt.co.kr 구형 경로), samilhan(segye.com www 정규화)

> 합계 53(확보) + 1(실패) = 54.

## 실패 목록(미아카이브)

| 파일 | 위치 | 원본 URL | 사유 | 비고 |
|---|---|---|---|---|
| `new_term--seunsangnim.json` | evidence[0] | http://www.newstomato.com/one/view.aspx?seq=465910 | available/CDX 스냅샷 없음 + `save` 저장 실패(재시도 1회 포함) | 해당 파일의 유일 출처. 사람 검수 시 보조 출처 추가 또는 수동 아카이브 권장. |

## URL → archive_url 전체 매핑

### `incident--boiru-yunjiseon-paper.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.seoul.co.kr/news/society/law/2023/09/30/20230930500052 | https://web.archive.org/web/20260605063234/https://www.seoul.co.kr/news/society/law/2023/09/30/20230930500052 | 기존 스냅샷 |

### `incident--ebs-pengsoo-deulkyeotno.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.mt.co.kr/society/2025/11/06/2025110606011416157 | https://web.archive.org/web/20260605063510/https://www.mt.co.kr/society/2025/11/06/2025110606011416157 | 기존 스냅샷 |

### `incident--gs25-camping-poster.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.seoul.co.kr/news/newsView.php?id=20210502500087 | https://web.archive.org/web/20230202104716/https://www.seoul.co.kr/news/newsView.php?id=20210502500087 | 기존 스냅샷 |

### `incident--h-homeshopping-yeogwon-sujeo.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://segye.com/newsView/20260527507034 | https://web.archive.org/web/20260605063615/https://segye.com/newsView/20260527507034 | 기존 스냅샷 |

### `incident--lotte-giants-nomuhan-baksu.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.news1.kr/society/general-society/6162899 | https://web.archive.org/web/20260605022728/https://www.news1.kr/society/general-society/6162899 | 기존 스냅샷 |

### `incident--maplestory-angelicbuster.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.seoul.co.kr/news/society/2023/11/26/20231126500042 | https://web.archive.org/web/20260605063843/https://www.seoul.co.kr/news/society/2023/11/26/20231126500042 | 기존 스냅샷(CDX) |

### `incident--renault-korea-inside.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.hankookilbo.com/News/Read/A2024070109320005575 | https://web.archive.org/web/20251202102154/https://www.hankookilbo.com/News/Read/A2024070109320005575 | 신규 저장(save) |

### `incident--starbucks-tankday.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://www.mt.co.kr/society/2026/05/20/2026052013381185811 | https://web.archive.org/web/20260521050820/https://www.mt.co.kr/society/2026/05/20/2026052013381185811 | 기존 스냅샷 |

### `new_marker--jipge-songarak.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| source_url | https://ko.wikipedia.org/wiki/%EC%A7%91%EA%B2%8C%EC%86%90%EA%B0%80%EB%9D%BD_%EC%9D%8C%EB%AA%A8%EB%A1%A0 | https://web.archive.org/web/20260109055724/https://ko.wikipedia.org/wiki/%EC%A7%91%EA%B2%8C%EC%86%90%EA%B0%80%EB%9D%BD_%EC%9D%8C%EB%AA%A8%EB%A1%A0 | 신규 저장(save) |

### `new_term--503-number.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.newsis.com/view/NISX20260519_0003635639 | https://web.archive.org/web/20260520014959/https://www.newsis.com/view/NISX20260519_0003635639 | 기존 스냅샷 |
| evidence[1] | https://www.karnews.or.kr/news/articleView.html?idxno=23921 | https://web.archive.org/web/20260605064114/https://www.karnews.or.kr/news/articleView.html?idxno=23921 | 신규 저장(save) |

### `new_term--doenjangnyeo.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://ko.wikipedia.org/wiki/%EB%90%9C%EC%9E%A5%EB%85%80 | https://web.archive.org/web/20260225142001/https://ko.wikipedia.org/wiki/%EB%90%9C%EC%9E%A5%EB%85%80 | 기존 스냅샷 |
| evidence[1] | https://femiwiki.com/w/%EB%90%9C%EC%9E%A5%EB%85%80 | https://web.archive.org/web/20251220080249/https://femiwiki.com/w/%EB%90%9C%EC%9E%A5%EB%85%80 | 기존 스냅샷 |

### `new_term--eung-di.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://femiwiki.com/w/%EC%9D%91%EB%94%94 | https://web.archive.org/web/20260605064438/https://femiwiki.com/w/%EC%9D%91%EB%94%94 | 기존 스냅샷 |
| evidence[1] | https://sports.khan.co.kr/article/201801251522013 | https://web.archive.org/web/20260605064510/https://sports.khan.co.kr/article/201801251522013 | 기존 스냅샷 |

### `new_term--gunmusae.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://femiwiki.com/w/%EA%B5%B0%EB%AC%B4%EC%83%88 | https://web.archive.org/web/20260605064752/https://femiwiki.com/w/%EA%B5%B0%EB%AC%B4%EC%83%88 | 기존 스냅샷 |
| evidence[1] | http://www.etoday.co.kr/news/view/1796493 | https://web.archive.org/web/20260605064954/https://www.etoday.co.kr/news/view/1796493 | 기존 스냅샷(CDX) |
| evidence[2] | https://www.insight.co.kr/news/336442 | http://web.archive.org/web/20211107140853/https://www.insight.co.kr/news/336442 | 기존(이전 배치 유지) |

### `new_term--hannam.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://ko.wikipedia.org/wiki/%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD%EC%9D%98_%EC%9D%B8%ED%84%B0%EB%84%B7_%EC%8B%A0%EC%A1%B0%EC%96%B4_%EB%AA%A9%EB%A1%9D | http://web.archive.org/web/20260418160559/https://ko.wikipedia.org/wiki/%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD%EC%9D%98_%EC%9D%B8%ED%84%B0%EB%84%B7_%EC%8B%A0%EC%A1%B0%EC%96%B4_%EB%AA%A9%EB%A1%9D | 기존(이전 배치 유지) |
| evidence[1] | https://www.khan.co.kr/article/201511231546391 | http://web.archive.org/web/20260405041650/https://www.khan.co.kr/article/201511231546391 | 기존(이전 배치 유지) |

### `new_term--heobeo-heobeo.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.hankookilbo.com/News/Read/A2021031614060000740 | https://web.archive.org/web/20240702170731/https://www.hankookilbo.com/News/Read/A2021031614060000740 | 기존 스냅샷 |
| evidence[1] | https://www.newsis.com/view/NISX20210420_0001413064 | https://web.archive.org/web/20260605065222/https://www.newsis.com/view/NISX20210420_0001413064 | 기존 스냅샷 |

### `new_term--hongeo.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002842479 | https://web.archive.org/web/20260605065624/https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002842479 | 신규 저장(save) |
| evidence[1] | https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C | https://web.archive.org/web/20260412124658/https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C | 기존 스냅샷 |
| evidence[2] | https://www.huffingtonpost.kr/article/257466 | https://web.archive.org/web/20260605022359/https://www.huffingtonpost.kr/article/257466 | 기존 스냅샷 |

### `new_term--jeolladian.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002842479 | https://web.archive.org/web/20260605065624/https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002842479 | 신규 저장(save) |
| evidence[1] | https://www.asiae.co.kr/article/2019062609313729121 | http://web.archive.org/web/20190822085141/https://www.asiae.co.kr/article/2019062609313729121 | 기존(이전 배치 유지) |
| evidence[2] | https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C | https://web.archive.org/web/20260412124658/https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C | 기존 스냅샷 |

### `new_term--jwajom.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://news.nate.com/view/20130527n32981 | https://web.archive.org/web/20260605070309/https://news.nate.com/view/20130527n32981 | 신규 저장(save) |

### `new_term--kimchinyeo.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://go.seoul.co.kr/news/newsView.php?id=20150716003006 | https://web.archive.org/web/20260605034021/https://go.seoul.co.kr/news/newsView.php?id=20150716003006 | 기존 스냅샷 |
| evidence[1] | https://femiwiki.com/w/%EA%B9%80%EC%B9%98%EB%85%80 | https://web.archive.org/web/20260218023108/https://femiwiki.com/w/%EA%B9%80%EC%B9%98%EB%85%80 | 기존 스냅샷 |

### `new_term--mamchung.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.hankookilbo.com/News/Read/201910251131797081 | https://web.archive.org/web/20240614145511/https://www.hankookilbo.com/News/Read/201910251131797081 | 기존 스냅샷 |
| evidence[1] | https://femiwiki.com/w/%EB%A7%98%EC%B6%A9 | https://web.archive.org/web/20251217022617/https://femiwiki.com/w/%EB%A7%98%EC%B6%A9 | 기존 스냅샷 |

### `new_term--no-ala.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C%EC%9D%98_%EC%82%AC%EA%B1%B4_%EB%B0%8F_%EC%82%AC%EA%B3%A0 | http://web.archive.org/web/20251117155109/https://ko.wikipedia.org/wiki/%EC%9D%BC%EB%B2%A0%EC%A0%80%EC%9E%A5%EC%86%8C%EC%9D%98_%EC%82%AC%EA%B1%B4_%EB%B0%8F_%EC%82%AC%EA%B3%A0 | 기존(이전 배치 유지) |
| evidence[1] | https://sports.khan.co.kr/article/201308211032243 | http://web.archive.org/web/20241229031440/https://sports.khan.co.kr/article/201308211032243 | 기존(이전 배치 유지) |
| evidence[2] | https://www.mt.co.kr/society/2013/08/20/2013082021001795850 | https://web.archive.org/web/20130823052538/https://news.mt.co.kr/mtview.php?no=2013082021001795850 | 기존 스냅샷(URL 정규화) |

### `new_term--no-ending-pattern.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.mt.co.kr/society/2025/11/06/2025110606011416157 | https://web.archive.org/web/20260605063510/https://www.mt.co.kr/society/2025/11/06/2025110606011416157 | 기존 스냅샷 |
| evidence[1] | https://www.xportsnews.com/article/2075070 | https://web.archive.org/web/20251212060154/https://www.xportsnews.com/article/2075070 | 기존 스냅샷 |
| evidence[2] | https://ko.wikipedia.org/wiki/동남_방언 | https://web.archive.org/web/20260121134322/https://ko.wikipedia.org/wiki/%EB%8F%99%EB%82%A8_%EB%B0%A9%EC%96%B8 | 기존 스냅샷 |

### `new_term--nomu.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.khan.co.kr/article/202006231420001 | https://web.archive.org/web/20260605022623/https://www.khan.co.kr/article/202006231420001 | 신규 저장(save) |
| evidence[1] | https://www.news1.kr/society/general-society/6162899 | https://web.archive.org/web/20260605022728/https://www.news1.kr/society/general-society/6162899 | 기존 스냅샷 |
| evidence[2] | https://www.newsis.com/view/NISX20260512_0003625546 | https://web.archive.org/web/20260513072833/https://www.newsis.com/view/NISX20260512_0003625546 | 기존 스냅샷 |

### `new_term--ojo-oeok.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.newsis.com/view/NISX20210420_0001413064 | https://web.archive.org/web/20260605065222/https://www.newsis.com/view/NISX20210420_0001413064 | 기존 스냅샷 |
| evidence[1] | https://www.wikitree.co.kr/articles/640742 | http://web.archive.org/web/20210420083838/https://www.wikitree.co.kr/articles/640742 | 기존(이전 배치 유지) |
| evidence[2] | https://www.hankookilbo.com/News/Read/A2021042110280003760 | https://web.archive.org/web/20210511063408/https://www.hankookilbo.com/News/Read/A2021042110280003760 | 기존 스냅샷 |

### `new_term--ottoke.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.hankookilbo.com/News/Read/A2022021514300002379 | https://web.archive.org/web/20220216114827/https://www.hankookilbo.com/News/Read/A2022021514300002379 | 기존 스냅샷 |
| evidence[1] | https://www.khan.co.kr/opinion/yeojeok/article/202202152122005 | https://web.archive.org/web/20220707003931/https://www.khan.co.kr/opinion/yeojeok/article/202202152122005/ | 기존 스냅샷 |
| evidence[2] | https://www.seoul.co.kr/news/newsView.php?id=20210418500025 | https://web.archive.org/web/20210514083941/https://www.seoul.co.kr/news/newsView.php?id=20210418500025 | 기존 스냅샷 |

### `new_term--samilhan.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://go.seoul.co.kr/news/newsView.php?id=20150716003006 | https://web.archive.org/web/20260605034021/https://go.seoul.co.kr/news/newsView.php?id=20150716003006 | 기존 스냅샷 |
| evidence[1] | https://www.mt.co.kr/society/2014/10/08/2014100823005853014 | https://web.archive.org/web/20260605034019/https://www.mt.co.kr/society/2014/10/08/2014100823005853014 | 기존 스냅샷 |
| evidence[2] | https://www.segye.com/newsView/20210825511203 | https://web.archive.org/web/20260605070559/https://www.segye.com/newsView/20210825511203 | 기존 스냅샷(URL 정규화) |

### `new_term--seunsangnim.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | http://www.newstomato.com/one/view.aspx?seq=465910 | **없음(미아카이브)** | 실패 |

### `new_term--ung-aeng-ung.json`

| 위치 | 원본 URL | archive_url | 방식 |
|---|---|---|---|
| evidence[0] | https://www.mt.co.kr/society/2020/01/06/2020010610024713207 | https://web.archive.org/web/20260605023156/https://www.mt.co.kr/society/2020/01/06/2020010610024713207 | 기존 스냅샷 |
| evidence[1] | https://www.newsis.com/view/NISX20210420_0001413064 | https://web.archive.org/web/20260605065222/https://www.newsis.com/view/NISX20210420_0001413064 | 기존 스냅샷 |
