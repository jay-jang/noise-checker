# 시드 2차 배치 적대적 검증 — 2026-06-05

6갈래 리서치 산출물 44건 전부 통과(구조적 반려 0) — 단 검증자가 직접 수정·draft 강등한 항목 다수 (날조 의심 단정문 제거: 개저씨·운지 등).
워크플로우 검증 에이전트 보고 원문:

## misandry

8건 전부 통과 (구조적 반려 0건). 스키마 검증 8/8 OK. 모든 evidence URL을 WebFetch로 직접 재확인했고, archive_url 5건은 HTTP 200 실재 확인(WebFetch가 web.archive.org 접근 불가라 curl로 검증). 나무위키/커뮤니티 직접출처 없음. 라이선스 라벨 규약 일치(wiki=CC BY-SA 4.0 share_alike, news=언론사 저작권(사실 추출만) permissive). 표면형 중복 없음 — 6개 surface(재기/씹치남/숨쉴한/한남유충/2번남/개저씨) 모두 큐 dedup 목록 및 후보셋 내 중복 없음.

### 통과 (그대로 둠)

- **new_term--jaegi.json** — 재기. femiwiki excerpt('자살 뜻 + 운지 비교') 원문 일치, 위키백과 '성재기 한강 실족 사건' 확인, 일요신문 혜화역 '문재인 재기해' usage 확인('재기해=성재기 한강 투신 희화화' 원문 일치). ambiguity=ambiguous + safe_contexts 6건, severity 5, legal_review_flag=true — 고인 실명 결합으로 보수적 처리 적절. 수정 없음.
- **new_term--ssipchinam.json** — 씹치남. 서울신문(씹치남=한국 남성 비하 속어)·페미위키(김치녀→성별/앞글자 교체 미러링, 2016 이후 사장) 양측 원문 확인. unambiguous 타당(연속문자열 '씹치남'은 일상어 충돌 없음). negative_example '김치남도(전라남도식 김치)'는 작위적 글로스이나 must_pass에 무해하여 surgical 원칙상 미수정. 수정 없음.
- **new_term--sumswilhan.json** — 숨쉴한. 서울신문이 '숨쉴한=삼일한 미러링, 숨 쉴 때마다 패야' 원문 확인. 단일 청정 뉴스 출처지만 핵심 주장 직접 뒷받침. severity 5(신체폭력 정당화 함의) 적절. unambiguous — 연속문자열 충돌 없음(공백 끼면 미매칭). 수정 없음.
- **new_term--hannam-yuchung.json** — 한남유충. 여성신문(미러링 vs 아동혐오 병존 + '어머니에게 책임 전가' 반론 verbatim)·뉴시스('-충' 계열 남아 비하) 확인. 기존 '한남' 항목과 별개 표면형(age 카테고리 교차, 변형이 아닌 독립 신조어)이라 중복 아님. ambiguity=ambiguous + safe_contexts(유충/한남동) 적절. 수정 없음.
- **new_term--ibeonnam.json** — 2번남. 서울경제가 '2번남=반여성 낙인 + 손절 + 1번녀 대칭' 확인. ambiguity=common이라 스키마상 combination_rules + trigger_evidence 필수 — 둘 다 존재·검증 통과. 차단 출처(조선일보) 제외하고 직접 확인된 서울경제만 채택한 처리 정직. 수정 없음.
- **incident--hannamchung-moyok-judgment.json** — 한남충 개인 지칭 모욕죄 유죄. 여성신문 115864가 '서울서부지법 강희경 판사, 17일, 벌금 30만원' verbatim 확인. related_surface=한남충 연결 적절. 수정 없음.
- **incident--seongjaegi-10ki-mockery.json** — 성재기 10주기 조롱글. 인사이트 445404가 '재기절 제삿상 구경하기'(여성시대 카페) 확인. occurred_at=2023-07-26(투신 2013-07-26의 10주기) 일치. 수정 없음.

### 통과 (수정 후) — 날조 의심 단정문 제거 + draft 강등

- **new_term--gaejeossi.json** — 개저씨. **결함: origin_story에 출처 없는 통계 단정문(보이루 선례 패턴).** 본문이 '다음소프트 분석 2011년 159회→2015년 약 7만6천 회 급증', '로이터·인디펜던트·르몽드 등 해외 언론 소개'를 사실로 단정했으나, 인용된 두 evidence(페미위키=세대 공격, 경향=정의) 어디에도 없고 WebSearch로도 다음소프트 수치·해외언론 음차 주장을 확인 못 함(SBS 스페셜 N1003464924 본문에도 해당 통계 없음). **수정 ①** 미확인 단정 두 문장 삭제, SBS 스페셜 부분만 유지하되 검증된 사실로 정정('2016년 3월 SBS 스페셜 「아저씨, 어쩌다 보니 개저씨」'). **수정 ②** needs_verification=false→**true** (draft 적재). 핵심 정의·세대공격 양면성은 페미위키+경향으로 견고히 뒷받침되어 전체 반려는 과함 → draft 통과. 수정 후 스키마 재검증 OK.

## disability

배치 9건 전수 검증. 전부 통과(반려 0). 모든 evidence URL을 WebFetch로 직접 재확인했고 surface의 의미·유래·심각도 주장을 실제로 뒷받침함을 확인. 나무위키·커뮤니티 직접 출처 없음. 기존 큐 표면형 목록과 중복 없음(절름발이/외눈박이/벙어리/귀머거리/결정장애/애자/병신/눈뜬장님/정신병자 9개 모두 후보·큐 내 단일). 전 파일 `validate_candidates.py` 통과.

### 핵심 출처 재확인 (실재+주장 일치)
- 한국경제 2014(`/article/2014110392201`): 인권위가 '귀머거리·벙어리·장님·절름발이' 공적 영역 자제 의견표명 + 진정 174건 — 절름발이/벙어리/귀머거리/눈뜬장님 4개 파일의 정의 근거로 정확.
- 경향신문 2022(`202204151652001`)·한국일보 2024(`A2024032816530000154`): 곽상도'외눈박이 대통령'·이광재'절름발이 정책'·허은아'집단적 조현병'·윤희숙'정신분열적'·김은혜'꿀 먹은 벙어리', 법원 '매우 부적절하나 배상책임 없음' 기각 — 본문 일치.
- 한국경제 2019(`201908094739Y`)·비마이너 2019(`idxno=13719`): 황교안 '벙어리' 발언, 8개 장애인단체 규탄 — 일치.
- 파이낸셜뉴스 2018(`201811010914262366`): '너 애자(장애인 비하 표현)냐'·'저러니 병신 낳지' — 애자/병신 직접 명시 확인.
- 에이블뉴스 2025(`idxno=221296`): 김용현 '병신' 국감 발언 + 홍준표·이철우 '정신병자' 진정·행정심판 — 일치.
- 슬로우뉴스 2016(`/57952`)·위키백과 병신(동음이의): '병신 짓=장애인 같은 짓' 분석, 病身(욕설)/丙申(간지) 구분 — 일치, byeongsin의 CC BY-SA 4.0 라벨 적정.
- 아주경제 2021(`20210725115150171`)·한글문화연대 2021(`urimal.org/3640`): '결정장애/선택장애'·'꿀 먹은 벙어리' 차별 표현 설명 — 일치.

### 날조 검사
- 단정문 유래 없음. 어원 헤지 적절: **aeja** — '장애자 파생' 통설을 청정 출처가 어원으로 직접 명시하지 않아 `needs_verification=true`로 draft 고정(적절). 나머지는 '전통적 표현, 시점 불명'으로 보수 서술.
- **byeongsin** origin_story의 "국립국어원 '장애인 차별 언어' 연구" 언급 → 실재 확인(중앙대 임영철 책임, 국립국어원 국고보조 '장애인 차별언어의 양태에 관한 연구'). evidence 배열에 URL은 없으나 정의 핵심은 위키백과+슬로우뉴스+FN뉴스로 입증되므로 narrative 보조 서술로 허용.

### 직접 수정 (경미 결함, 통과 처리)
- **beongeori / gyeoljeongjangae / nuntteunjangnim**: `urimal.org`(한글문화연대) 출처의 `source_type`을 `"wiki"` → `"news"`로 교정. 해당 출처는 CC BY-SA 위키가 아니라 단체 칼럼(명시 필자) — `wiki` 라벨은 share_alike 추적을 오도할 수 있음. `license: permissive`는 원래 정확해 라이선스 게이트 영향 없음. 수정 후 3건 재검증 통과.

### 보수성 점검 (수정 불필요)
- ambiguity 보수적: 절름발이·결정장애·눈뜬장님=common(단독 매칭 금지, combination_rules+trigger_evidence 구비) / 외눈박이·벙어리·귀머거리·애자·병신·정신병자=ambiguous(safe_contexts 구비). 동음이의(병신년 干支, 외눈박이 물고기, 벙어리장갑, 결정장애↔발달장애 등) 모두 safe_contexts·negative_examples로 처리됨. unambiguous로 과대 설정된 항목 없음 → safe_contexts 추가 수정 불요.
- **gwimeogeori**: 직접 정의는 한국경제 2014('귀머거리' 명시 포함) 단일 청정 출처에 의존, 비마이너는 본문에 '귀머거리' 부재한 인접 맥락 출처(파일 _comment가 이미 정직하게 고지, excerpt도 '벙어리' 발언 기준으로 교정됨). 정의가 1차 출처로 직접 뒷받침되므로 `needs_verification=false` 유지 가능하나, 사람 검수 시 청정 정의 출처 1건 보강 권장.
- legal_review_flag=false 일괄 적정: 용어 자체는 일반어/욕설이고 실명은 related_incidents 사례 인용에만 등장. 정치인 사례 인용 시 사람 검수 권장(파일 _comment에 기재됨).

## deceased-ilbe

적대적 재검증 결과: **6건 전부 통과** (반려 0). 구조적 결함(출처 부적격·중복) 없음. 날조 의심 1건은 직접 수정 후 needs_verification=true로 통과(draft 적재). 모든 evidence URL을 WebFetch로 직접 재확인했고 전부 실재·주장 뒷받침 확인. namu.wiki·커뮤니티 직접 출처 없음. validate_candidates.py 6/6 OK.

### 파일별 판정

**new_term--unji.json — 통과(직접 수정, needs_verification=true)**
- ① 출처 재확인: ko.wikipedia '운지'(노무현 자살 비하 일베 용어 정의, 문구 일치), 한국일보(운지천 CF→투신 희화화), 스포츠월드(최민식 절벽 CF 유래) 전부 실재·뒷받침 확인.
- ③ **날조 의심 발견 → 수정**: origin_story가 "노무현 얼굴을 합성한 동영상이 만들어지면서 시작됐고"와 "dcinside(합성갤 발원)"를 단정문으로 서술. 그러나 인용 출처(스포츠월드)에 '얼굴 합성 동영상 제작'·'dcinside 합성갤 발원' 서술은 없음(WebFetch로 부재 확인) — 보이루 선례형 과잉 단정. **수정 내역**: (a) origin_story를 출처가 실제 뒷받침하는 범위(운지천 CF 빗댐→2009 투신 비하→일베 확산)로 축소하고 미확인 세부는 명시적으로 제외 처리, (b) origin_community `dcinside`→`ilbe`, spread_communities에서 'dcinside(합성갤 발원)' 제거, (c) origin_period "2011년경"→"2009년 이후, 세부 미확정"(스포츠월드의 2011년은 '일베 창설' 연도이지 용어 발생 연도가 아님), (d) needs_verification false→true, (e) _comment의 '디시 합성갤 발원' 문구 제거.
- ② 라이선스: wiki=CC BY-SA 4.0(share_alike), 뉴스=사실 추출만(permissive) 라벨 정확.
- ⑥ ambiguity=ambiguous + safe_contexts(운지버섯/운지법) + negative_examples 3건 — 동음이의 보수 처리 적절. severity=5, legal_review_flag=true 타당. ambiguous는 스키마상 combination_rules 비필수(common/number만 필수)라 OK.
- ④ 중복 없음(기존 큐에 예시 픽스처만 존재, 정식 후보 미존재).

**new_term--eomuk.json — 통과(무수정)**
- ① ko.wikipedia 일베 사건사고('어묵'=세월호 단원고 학생 비하, 야구갤 발원, 문구 일치), 헤럴드경제(어묵데이/손가락 인증), 뉴시스(징역4월 실형), 경향(항소심 실형) 전부 실재·뒷받침. origin_story의 '친구 먹었다'·'어묵데이'·실형 선고 등 핵심 서술 모두 출처로 확인됨(날조 없음).
- ② 라이선스 라벨 정확. ⑥ ambiguity=common → combination_rules+trigger_evidence 구비(스키마 충족), 단독 base_severity=1 / 세월호·단원고 동시출현 시 +4 = 보수적 설계 적절. severity=5, legal_review_flag=true 타당. ④ 중복 없음.

**new_term--minjuhwa.json — 통과(무수정)**
- ① 한국일보(광주민주화운동 빗대 '억압'), 뉴시스(전효성 발언, 일베서 '하향평준화/죽음' 부정 의미), 세계일보(소수 집단폭행/언어폭력 은어) 전부 실재·뒷받침. origin_story 사실 부합.
- ② 출처 전부 뉴스(permissive, 사실 추출) — 라벨 정확. ⑥ 5·18 민주화운동 등 표준어와 완전 동철 → ambiguity=common + combination_rules + trigger_evidence + safe_contexts 9건 + negative_examples 3건으로 동음충돌 보수 처리 우수. severity=3(단독 정상어)로 보수적, 적절. legal_review_flag=false 타당(특정인 비방 아님). ④ 중복 없음.

**incident--hongeo-taekbae-518-judgment.json — 통과(무수정)**
- ① mt.co.kr 실재·뒷받침: 5·18 희생자 관 '홍어택배' 칭, 유가족 사진 택배송장 합성, 대법원 모욕죄 확정 징역6월 집유1년 사회봉사80시간 — 페이로드와 일치. ② 출처 뉴스(permissive). 스키마 incident 필수필드(related_surface='홍어택배') 충족, validate OK. ④ '홍어택배'를 독립 신규 용어로 단정하지 않고 모욕죄 확정 실사고로만 기록 — 적절(기존 '홍어' 용어와 표면형 중복 아님).

**incident--sewol-eomuk-judgment.json — 통과(무수정)**
- ① 뉴시스 실재·뒷받침: 세월호 '어묵' 모욕 일베 회원 2명 징역4월 실형(집유 없음), 재판부 "연예인·정치인 아닌 어린 학생" 지적 — 페이로드와 일치. ② permissive. eomuk 용어 후보와 연결되는 독립 incident, related_surface='어묵', validate OK. ④ 중복 없음.

**incident--jeonhyoseong-minjuhwa.json — 통과(무수정)**
- ① 뉴시스 실재·뒷받침: 시크릿 전효성 라디오 '민주화시키지 않는다' 발언, 일베식 표현 논란, 당일 사과 — 페이로드와 일치. ② permissive. '민주화'를 혐오어로 단정하지 않고 반어적 오용 보도 사실만 기록 — 적절. related_surface='민주화', medium=broadcast, validate OK. ④ 중복 없음.

### 종합
- 라이선스 게이트 관점: 모든 항목 evidence가 permissive(뉴스) 또는 share_alike(위키백과)만 사용 — 릴리스 게이트 통과 가능. unji의 위키백과(CC BY-SA) 유래 서술은 build 시 provenance_class=share_alike_core로 응답 비노출 기본값 적용 대상이나, 매칭/차단 동작에는 영향 없음.
- 적재 상태: unji는 needs_verification=true로 draft 적재(세부 유래 인간 검증 대기), 나머지 5건은 정상 후보로 적재.

## region

적대적 재검증 결과: 5건 전부 **통과 (수정 없음)**. 구조적 결함(출처 부적격·날조·중복) 없음, rejected 이동 0건, 직접 수정 0건. 모든 evidence URL을 WebFetch로 라이브 재확인했고 인용 excerpt가 원문과 일치함.

### 공통 검증
- **출처 적격성(②)**: 전부 뉴스(permissive, '언론사 저작권(사실 추출만)') 또는 학술. namu.wiki·커뮤니티 직접 출처 0건. 각 파일 `_comment`에 '나무위키 미기록' 명시됨.
- **중복(④)**: 5개 표면형(개쌍도/멍청도/감자국/과메기/깽깽이) 모두 dedup 목록·기존 후보 파일과 비충돌. dedup 목록 단어(홍어·전라디언·503 등)는 evidence/유래의 **교차 참조**로만 등장, surface 아님.
- **스키마(⑤)**: `validate_candidates.py` 5건 전부 OK.

### 파일별 판정

**new_term--gaessangdo.json (개쌍도) — 통과**
- SBS(N1003128014, 2015-08-18)·세계일보(20130312004785, 2013-03-13)·서울신문(20150323002016, 2015-03-23) 전부 실재, 인용 일치. 서울신문이 '멍청도'(충청)·'개쌍도'(경상)·'홍어'(전라) 지역 매핑을 그대로 확인.
- ambiguity=unambiguous 적절: '개쌍도'는 동철 일반어 없는 순수 조어. severity 4 보수적. 유래 서술('국회 정개특위 선거법 처벌 예시 거론')은 SBS 처벌 기사 맥락이 뒷받침. 날조 없음.

**new_term--meongcheongdo.json (멍청도) — 통과**
- 가장 위험한 단정성 유래(1988년 제13대 총선 부여 유세 최초 사용)를 오마이뉴스(A0001631472) 원본에서 직접 확인: 후보 임두빈 "멍청도라는 이름 청산" 유세 기록 + '정치적으로 조장된 지역감정' 서술 일치. origin_story가 "보도에 따르면…거론된다"로 적절히 헤지 → 보이루식 날조 아님.
- 서울신문·SBS(N1003409358) 보조 출처 확인. ambiguity=unambiguous지만 방어적 safe_contexts('멍청하다','충청도' 등) 보유 — 스키마상 무해, 검출 안전성 향상. 수정 불필요.

**new_term--gamjaguk.json (감자국) — 통과**
- 서울신문(감자국=강원 매핑 직접 확인)·시사저널(136928, 2013-03-12: '감자도'=강원 신조어 목록 확인)·아주경제(20160510…: '감자바우' 애칭→비하 변질 확인) 전부 실재. 
- 경미 불일치(반려 사유 아님): 시사저널 excerpt에 영남을 '경상디언'으로 적었으나 원문은 '경상 흉노'. 단, 적재 대상 표면형은 '감자국'이고 load-bearing 주장(감자도=강원 지역비하 신조어)은 견고. 아주경제 '5·15부정선거'는 원문 자체가 '속설'로 명시한 추정이라 origin_story도 '1950년대 선거 이후'로 헤지.
- ambiguity=ambiguous + 음식 safe_contexts(감자 넣은 국·감자옹심이 등) 충실 → 보수적·정확. severity 3 적절.

**new_term--gwamegi.json (과메기) — 통과**
- 한국일보(우리말 톺아보기, 2019, 이정복 교수: "'홍어'와 '과메기'…해당 지역민들을 부정적으로 가리키는 데 쓰인다" 인용 일치)·SBS·세계일보 전부 확인.
- ambiguity=common 정확(음식명 압도). 스키마 요구대로 combination_rules + trigger_evidence 구비, trigger_evidence URL 3건 실재 확인. base_severity 1 + delta 3 → 지역·인물 타깃 결합 시에만 위험으로 보수 설계. 단독 음식 언급 미검출 보장. 수정 불필요.

**new_term--kkaengkkaengi.json (깽깽이) — 통과**
- KCI 양혜승(2022, '지역과 커뮤니케이션' 26(2), 36-70) 초록에서 "'홍어','홍어족','전라디언','깽깽이' 도출" 직접 확인(reliability 5). 노컷뉴스(241846, 2007-01-26)도 "전라디언…깽깽이, 깡패…" 호남 비하 악플 인용 확인.
- 유래(전라도 말씨→개 깨갱 빗댐)는 origin_story에서 '속설'로 명시 → 날조 아님. ambiguity=ambiguous + safe_contexts(깽깽이걸음·해금·깽깽이풀) 충실 → 동철 일반어(악기·외발뛰기·들꽃) 충돌 방어 정확. severity 4는 슬러 사용 시 내재 강도이고 ambiguity가 분리 처리하므로 일관됨.

## misogyny-jargon

적대적 재검증 결과 7건 전부 유지(통과). 구조적 결함(출처 부적격 실제 인용·중복·날조 단정)으로 reject한 파일 없음. 2건은 경미/중간 결함을 직접 수정 후 통과 처리. rejected/ 디렉터리 생성 없음.

스키마 검증: 7건 전부 `validate_candidates.py` OK. 표면형 중복 검사: 기존 큐(503·된장녀·응디·군무새·한남·허버허버·홍어·전라디언·좌좀·김치녀·맘충·노알라·노무·오조오억·오또케·삼일한·슨상님·웅앵웅·집게손/한남유충 등)와 7개 surface(김여사·성괴·상폐녀·보슬아치·페미나치·꼴페미·흉자) 모두 충돌 없음. 나무위키를 evidence로 직접 인용한 파일 없음.

### 1. gimyeosa (김여사) — 통과 (무수정)
- evidence 3종 WebFetch 재확인 전부 실재·일치: 페미위키(CC BY-SA 4.0, "2006년 4월 중순 '김여사 놀이'", 운전 서툰 중년 여성 비하 정의 확인) / 경인일보 2024(인천시 유튜브 '운전 배우는 김여사' 여성비하 빈축, 문체부 "운전 미숙자가 여성일 것이라는 고정관념" 지적 확인) / 한국일보 2019 AMP(서울시여성가족재단 '김여사→운전미숙자' 성평등 언어 제안, 성차별 언어로 명시 — 접속·내용 확인).
- ambiguity=common이며 스키마 강제대로 combination_rules + trigger_evidence(경인일보·한국일보) + safe_contexts 구비. 동음 인명 호칭('김 여사님', '이순자 여사')과 negative_examples로 분리. license_class: 뉴스=사실 추출, 위키=CC BY-SA 라벨 정확. legal_review_flag=false 타당(일반 멸칭).

### 2. seonggoe (성괴) — 통과 (무수정)
- evidence 3종 실재·일치: 헤럴드경제 2013(웹툰 유래·'성괴학교/졸업식' 파생, origin 확인) / SBS 2015(성괴를 김치녀·오크녀·상폐녀와 함께 온라인 여성혐오 표현으로 분류 확인) / 페미위키(CC BY-SA, 정의 확인). 라벨 정확, 나무위키 미사용.
- severity 4 보수적 타당. ambiguity=ambiguous + safe_contexts(고유명사 약칭 등) 적절.

### 3. sangpyenyeo (상폐녀) — 통과 (수정함, needs_verification=true)
- **적대적 발견**: origin_community="dcinside" 및 origin_story의 "디시인사이드 (구)주식 갤러리 발원" 단정 서술이 인용된 적격 출처(페미위키·SBS)에 없음. 페미위키 본문 WebFetch 재확인 결과 "발원처 미명시"였고, dcinside 주갤 발원설은 나무위키·개인 블로그에만 존재(=게이트 부적격 출처). 보이루식 무출처 유래 단정 위험.
- **수정**: (a) origin_community "dcinside"→"other", (b) origin_story에서 dcinside 단정 제거하고 "적격 출처에서 확인되지 않아 단정하지 않는다"로 명시 완화, (c) needs_verification=false→**true**(draft 적재). 의미·여성혐오 성격 자체(페미위키 '상장폐지된 여성', '크리스마스 케이크' 결합 + SBS '노처녀 비하·팔리지 않는 물건' 설명)는 출처로 확실히 뒷받침되어 유지. 재검증 OK.

### 4. boseulachi (보슬아치) — 통과 (무수정)
- evidence 3종 전부 실재·일치(가장 견고): 페미위키(CC BY-SA, '보지+벼슬아치' 합성, "1990년대 후반 PC통신발", "현재 의미는 2011년 일베저장소 초기·디시" 원문 그대로 확인) / CBS노컷뉴스 2013("여성 성기에 빗대 여자인 게 벼슬인 줄 안다는 일베어" 정의 확인) / 경향신문 강신주 칼럼 2014(여성 성기어+벼슬아치 합성, 성취한 여성에게도 무차별 적용·파시즘 비유 비판 확인).
- severity 5(노골적 성적 모욕) 타당. unambiguous 적절(무해 동철 없음).

### 5. feminachi (페미나치) — 통과 (무수정)
- evidence 2종 실재·일치: 한국어 위키백과(CC BY-SA, 1989 등장·러시 림보 확산·홀로코스트 모독 비판 확인 — 단 '꼴페미' 언급은 WP엔 없음) / 페미위키 페미나치(CC BY-SA, "래디컬 페미니스트 비하", "한국어로 현지화하면 꼴페미(꼴통+페미니스트)라고 한다" 원문 확인). origin_story의 "페미위키가 꼴페미를 대응어로 든다" 서술은 페미위키 출처로 정확히 뒷받침됨(WP가 아님). 라벨·출처 적격.

### 6. kkolpemi (꼴페미) — 통과 (수정함)
- **적대적 발견**: evidence #2가 "위키백과 페미나치" URL을 인용하며 "한국어로 현지화하면 꼴페미에 해당한다는 맥락이 서술됨"이라 적었으나, 위키백과 페미나치 본문 WebFetch 재확인 결과 **꼴페미 언급 자체가 없음**(오귀속/excerpt 날조). 실제 해당 서술은 페미위키 페미나치 페이지에 존재.
- **수정**: evidence #2의 URL을 위키백과→페미위키 페미나치(`/w/페미나치`)로 교체, publisher·excerpt를 실제 본문("꼴통+페미니스트" 명시)으로 정정, reliability 4→3(wiki). _comment에 수정 경위 명기. evidence #1(페미위키 꼴페미, 정의·비하 분류) 단독으로도 surface 의미 뒷받침되어 통과 유지. 재검증 OK.

### 7. hyungja (흉자) — 통과 (무수정)
- evidence 2종 실재·일치: KCI 고은해(2019) 논문(서지 정확 — '미디어, 젠더 & 문화' Vol.34 No.4, pp.53-97, 한국여성커뮤니케이션학회, DOI 확인; 초록의 "'다른 여성' 비난 기제·여성혐오 메커니즘 반복" 분석 확인) / 페미위키 흉자(CC BY-SA, '흉내자지' 줄임·워마드 생성·'명예남성' 부정 어감화 목적 원문 확인). academic=서지·사실 참조 라벨 적절.
- 표적이 '다른 여성'이라 misogyny+community_jargon 분류 타당. severity 4(비속 어근 포함) 보수적. ambiguity=ambiguous + safe_contexts(한자어/인명 약어 오인) 적절. 워마드 직접 접근 미사용(2차 출처만).

## incident-marker

검증자 결론: 9건 전부 통과(반려 0). 스키마 검증 9/9 OK. 출처 부적격(namu.wiki/커뮤니티 직접) 없음, 라이선스 라벨 정합, 표면형 중복 없음. 다만 페이로드에 출처 미뒷받침 단정문 2건을 발견해 직접 수정(BBQ 제목, 국방부 제목+needs_verification)했다. 구조적 결함이 없어 `data/seed/rejected/2026-06-05/`는 생성하지 않음.

### 증거 URL 재확인 (WebFetch 직접 + WebSearch 교차)
주의: `web.archive.org`는 본 환경 WebFetch가 차단 → 모든 archive_url은 직접 페치 불가. 대신 **원문(source_url) 직접 페치 + 독립 WebSearch 교차검증**으로 대체 확인.

- **incident--musinsa-jipge-songarak** — PASS. newsis 2021-05-03 원문 실재, 무신사×현대카드 손모양 논란·무신사 해명("의도 없음, 일반적 구도") 일치. 페이로드 제목의 "조만호 대표 2021-06 사임"은 출처 기사엔 없으나 **독립 확인됨**(2021-06-03 daum/hankookilbo: 성차별 쿠폰+이벤트 이미지 논란 책임 사임). 사실 정확 → 무수정 통과.
- **incident--musinsa-baeksang-tak** — PASS. newsis 2026-05-22 원문 실재. 정확 문구 "책상을 탁 쳤더니 억하고 말라서" 본문 등장, 조만호·조남성 박종철센터 방문 재사과, 박종철 고문치사 트로프 확인. related_surface '책상에 탁'은 기존 starbucks-tankday와 정합. 무수정 통과.
- **incident--bbq-jipge-songarak** — 경미 결함 수정 후 통과. hankookilbo 2021-05-07 원문 실재, BBQ 소떡 손모양 논란+즉시 사과 일치. **그러나 해당 출처에 교촌치킨 언급 없음**에도 페이로드 `title`에 "(교촌치킨 동시 논란)"이 들어가 있었음 — _comment는 "교촌은 _comment에만 부기"라 자칭했으나 실제론 제목으로 누출(날조성 단정 리스크). **제목에서 (교촌치킨 동시 논란) 제거** 수정. _comment의 교촌 메모는 보존.
- **incident--mnd-card-news-salute** — 결함 완화 후 needs_verification 통과. fnnews 2021-05-26 원문 실재, 거수경례 '집게 손'/'김정은식 경례' 논란 확인. **그러나 출처·독립검색 어디서도 "국방부의 사과+시정조치 완료"를 뒷받침하지 못함** — _comment의 따옴표 인용("경례 동작을 정확히 표현하지 못해 오해를 야기한 점 사과")은 출처 미확인 단정(보이루 선례형 리스크). 논란 자체는 실재하므로 반려 대신: **제목을 "…남혐 논란"으로 완화(사과·시정 삭제)** + **payload.needs_verification=true** 추가(draft 적재). 스키마 incidentPayload는 additionalProperties 미제한이라 검증 OK 재확인.
- **incident--kakaobank-songarak** — PASS. hankookilbo 원문 실재, 손모양 논란+사과+이미지 전량 삭제·전수조사 일치. 경미 불일치: 원문 입력일은 2021-05-28, 페이로드 occurred_at/제목은 2021-05-27 — 사과 시점(05-27) vs 기사 게재(05-28)로 합리적, 수정 불요.
- **incident--police-pm-cardnews** — PASS. hankyung 2021-05-02 원문 실재. PM(개인형이동장치)·도로교통법 카드뉴스, 경찰 해명("민간업체 제작, 페이지 강조용, 특정 단체 무관, 수정 중") 일치. _comment가 '제작자 40대 남성' 후속을 본 출처 미기재라며 단정 회피한 점 적절. 무수정 통과.
- **incident--pyeongtaek-poster** — PASS. asiae 2021-05-17 원문 실재. 평택시 입장("남성 혐오 의도 없으나 매우 유감")과 재제작 수량(현수막 23·포스터 200·전단 4000) 정확히 일치. 무수정 통과.
- **new_marker--megal-son** — PASS. femiwiki '메갈손' 문서 실재, 미러링 유래·'집게손가락 음모론' 회의론(디자이너 무의도 클립아트·셰도우 복싱) 본문 일치. **하단 라이선스 CC BY-SA 4.0 확인 → license_note의 share_alike 라벨 정합**. 의도성 미입증·반론 병기 원칙 준수. 기존 new_marker--jipge-songarak(손동작)과 _comment에서 명시적으로 구분(로고/엠블럼 자체) → 중복 아님. 무수정 통과.
- **new_marker--ilbe-son** — PASS. segye 2024-07-03 원문 실재, 손 형태 서술("엄지·검지로 원, 약지만 접어 ㅇㅂ") 페이로드와 정확 일치, 2015 청와대 폭파협박범 사례 포함. 보조 출처 경향신문 2016-05-31(홍대 ㅇㅂ 조형물, 작가 해명 "실체 없이 만연한 일베를 드러내려는 의도") 독립 확인. 언론=사실 추출(permissive) 라벨 정합. 집게손가락(메갈)과 손가락 구성·상징 상이 → 중복 아님. 무수정 통과.

### 중복 검사 결과
지시 dedup 리스트의 "집게손가락(marker)"은 기존 new_marker--jipge-songarak이며 본 검증 대상 아님. 대상 2개 신규 표식(megal-son=메갈리아 로고 엠블럼, ilbe-son=ㅇㅂ 손인증)은 jipge-songarak(일반 손동작) 및 리스트의 용어형 표면(503/된장녀/응디/군무새 등)과 표면형 중복 없음. incident 7건도 기존 GS25/르노/메이플 incident와 별개 사건. 중복 반려 없음.

### severity·ambiguity 검토
incident/new_marker kind는 term schema의 severity/ambiguity 필드를 강제하지 않으며(payload 계약 분리), 모든 표식 origin_note가 '단일 손모양만으로 자동 단정 금지 + 반론 병기'로 보수적으로 작성되어 동음이의/오탐 위험을 이미 흡수. safe_contexts 추가 불필요.
