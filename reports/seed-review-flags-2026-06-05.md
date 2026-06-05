# M1 시드 1차 배치 — 검증 플래그 (사람 검수용)

> 2026-06-05 리서치 워크플로 산출. 파일 28개, 스키마 검증 실패 0건, 플래그 112건.
> 아래 플래그는 적대적 검증자가 남긴 **사람 검수 주의사항**이다 (차단 사유 아님 — 검수 콘솔에서 승인 전 확인).

## incident--boiru-yunjiseon-paper.json
- occurred_at 일(day) 미확정: 게재 월(2019년 12월)은 출처로 확인되나 정확한 게재 '일'은 독립 확인 불가. KCI 동계호 관례에 따라 임시로 '2019-12-31' 사용 — 사람이 정확한 게재일 확인 또는 'occurred_at=2019-12'(월 단위)로 조정 검토 필요.
- incident의 occurred_at 의미 모호: 현재 값은 '논문 게재일' 기준. 사고의 핵심 전개(명예훼손 배상 확정 2023-03, 가톨릭대 상대 판정무효 소송 패소·논문철회 확정 2023-09)는 별개 시점. 검수자가 '사고 발생 기준일'을 게재일로 둘지 판결일로 둘지 정책 확정 권장.
- _comment의 '법원(2022~2023)' 표현 — 최종 확정은 배상 2023-03(상고 취하), 판정무효 2023-09. 2022는 하급심 추정이며 출처로 명시 확인하진 않음. 단정 표현 점검 권장.
- 민감 주제(실명 보겸·윤지선 포함, 미소지니 인접). 단 본 레코드는 incident이며 '보이루'를 혐오어로 단정하지 않고 법원이 그 규정을 배척한 사실을 기록 → new_term 미등재 정책 부합. legal 검토 대상 표식 유지 권장.
- URL 확인 완료: source_url(서울신문 seoul.co.kr/.../20230930500052) 접속 성공·해당 사건(보이루/윤지선/보겸 명예훼손·판정무효 패소)과 정확히 일치. 나무위키 출처 없음.

## incident--ebs-pengsoo-deulkyeotno.json
- occurred_at=2025-10-24는 문제 영상(자이언트 펭TV EP.415 '이번 수능 수학은 이걸로 끝') 업로드일 기준. 논란 보도/자막 삭제는 2025-11-05~06. _comment는 사건을 '2025-11'로 표기해 시점 기준이 혼재. 또한 출처(엑스포츠뉴스)는 업로드를 '지난달 25일'(10-25)로 기술해 검색 결과(10-24)와 1일 차이. occurred_at 자체는 자막 게시일 기준으로 타당하나 사람 검수 시 10-24 vs 10-25 확정 권장.
- related_surface='~노'는 일베의 노무현 전 대통령 비하 '-노' 종결어미 패턴(정치/지역 혐오 계열)이며 misandry 카테고리 아님 → 항목7(남혐 청정 evidence 강제) 비해당. 검수 시 must_catch 등록은 '~노' 단독이 아닌 어미 패턴 규칙으로 연결 필요(평서문 종결 '-노' 오탐 위험: 표준어 '하노라' 등). 오탐 가드 검토 권장.
- namu.wiki는 후보 파일에는 미사용(청정). 단 교차검증 웹검색 결과 목록에 namu.wiki 항목이 노출되었을 뿐이며 파일/evidence로 채택하지 않음.
- incident kind라 evidence/excerpt/license/severity/categories/safe_contexts/negative_examples 필드가 스키마상 부재(해당 정책 항목은 new_term/new_marker/candidate-term 대상). incidentPayload 필수항목(title, occurred_at, medium, source_url, related_surface) 모두 충족 및 스키마 통과 확인.

## incident--gs25-camping-poster.json
- 검토 결과 수정 없음 — 통과. 근거: 단일 출처 서울신문 기사가 핵심 사실(GS25 캠핑 포스터, 소시지 집게손 그래픽, 메갈리아 로고 유사 의혹, GS25 사과, 영문 슬로건 끝글자 'megal' 조합 주장)을 모두 직접 뒷받침함. URL 접근 정상.
- 이 항목은 incident kind라 categories/severity/evidence/excerpt/safe_contexts/license_note 필드가 스키마상 존재하지 않음(해당 필드는 term/marker용). 따라서 라이선스 표기·카테고리·excerpt 길이 점검은 incidentPayload에 비적용. 관련 검증은 source_url(뉴스, 사실 추출만)·sample_text(79자)로 한정 수행함.
- 남혐(misandry) 인접 사안이나 의도성 미입증 사건임. 파일이 이를 보수적으로 처리함: sample_text가 'megal' 조합을 '주장'으로 명시하고 _comment도 '의도성 미입증' 기재. 단정 없음 → needs_verification 강제 트리거 해당 없음. 연계 표식 파일 new_marker--jipge-songarak.json이 '의도성 미입증·반론 병기' 원칙을 보유.
- namu.wiki는 후보 파일 어디에도 없음(검증자 웹검색 결과에만 등장). 파일 _comment의 '나무위키 미사용' 선언 사실로 확인됨.
- occurred_at=2021-05-01(논란 시작일)과 출처 기사 작성일 2021-05-02은 1일 차이로 정합. related_marker가 new_marker--jipge-songarak.json의 name과 정확히 일치하여 향후 머지 연결 가능.

## incident--h-homeshopping-yeogwon-sujeo.json
- related_surface='홍어'는 프록시 연결: 실제 사고 문구('전라도 갈 땐 여권 대신 수저')는 홍어가 아니라 일베 계열 호남 지역비하 트로프임. _comment에 '가장 근접한 등재 후보 surface에 연결'로 명시돼 있으나, 사람 검수자가 프록시 surface 연결 정책 허용 여부를 확인 권장. 별도 호남 지역비하 surface(예: 여권/수저 트로프) 등재 시 재연결 검토.
- medium='ad'는 판단 보류 사항: 문제 콘텐츠는 H홈쇼핑 공식 유튜브 영상/인스타그램 게시물(홍보성)임. 광고/마케팅으로 보면 'ad', 채널 성격으로 보면 'sns'도 가능. 현 'ad'는 방어 가능하나 인접 사례(롯데 자이언츠 유튜브 자막=sns)와 medium 분류 일관성 검토 권장.
- occurred_at='2026-05-26'은 사고 표면화(JTBC 사건반장 보도)일 기준. 실제 콘텐츠 게시 시점은 기사에 '최근'으로만 표기돼 미상. 발생일 정의를 '게시일'로 본다면 차이 가능 — 출처 기준 보도일 채택은 합리적.

## incident--lotte-giants-nomuhan-baksu.json
- medium 분류 주의: 스키마 enum에 video/youtube 전용 값이 없어 공식 유튜브 자막 사고를 'broadcast'로 매핑함(형제 EBS 펭TV 케이스와 동일 규약). title에는 '공식 유튜브'로 명시되어 있어 enum과 표기가 어긋나 보일 수 있으니 사람 검수 시 분류 규약 확정 필요.
- occurred_at(2026-05-11)는 논란 발생·구단 공식 사과일과 동일(뉴시스 후속 보도 05-12). 원본 영상 업로드 정확 일자는 기사상 '금일 업로드'로만 확인되어 별도 명시되지 않음 — incident 기록으로는 무방하나 참고.
- 사실관계 자체는 news1·뉴시스·KNN·데일리안·머니투데이·서울신문·한국일보 등 다수 독립 출처로 강하게 교차 확인됨(노진혁 선수, 자이언츠 TV, '노무한 박수' 자막, 일베 논란, 구단 공식 사과, 협력사 직원 퇴사). 금지 출처(namu.wiki) 미사용. needs_verification 불요.

## incident--maplestory-angelicbuster.json
- 출처 검증 완료(WebFetch): source_url(seoul.co.kr) 기사는 실제 '남혐 캐릭터 논란… 넥슨·카카오게임즈 등 게임사 줄줄이 사과'(2023-11-26)로 엔젤릭버스터 집게손가락 사례와 정확히 일치. 나무위키 미사용 확인(파일 전체 grep, source_url 모두 청정).
- _comment의 '남성 애니메이터가 작업 → 의도성 반증' 주장은 독립 보도(SBS '0.1초 집게손', 서울경제 '그린 사람 정체', 아주경제)로 교차 확인됨: 문제 콘티는 뿌리가 아닌 타 업체 40대 남성 애니메이터 A씨가 담당, 총괄 감독도 50대 남성. 단, 청정 출처(서울신문) 기사 본문에는 '남성/40대' 세부가 명시되지 않을 수 있으니 _comment의 해당 단정을 게시할 경우 SBS/서울경제 출처 추가 권장.
- 이 항목은 misandry성 사례지만 kind=incident이며 스키마상 incident payload에는 categories/severity/ambiguity/safe_contexts/negative_examples/evidence/excerpt 필드가 없음. 검증 지침 4~8(term-level)은 본 파일 kind에 비적용. related_marker='집게손가락'은 별도 new_marker 후보(new_marker--jipge-songarak.json)와 연결되므로, misandry 청정 origin/definition 근거 요구(지침 7)는 marker 항목 검수에서 별도 확인 필요.
- occurred_at 날짜는 11-25(논란 발발 야간)와 11-26(사과·기사) 모두 사실로 보도됨. 출처 정렬 위해 26일로 수정했으나, 사건 '발발일' 기준으로 25일을 선호하면 사람 검수자가 재조정 가능(둘 다 방어 가능).

## incident--renault-korea-inside.json
- 인물 식별 가능성/법적 민감성: 본 incident는 르노코리아의 특정 개인(여성 브랜드매니저 'A씨')에 대한 직무정지 조치를 다룸. 실명은 없으나 식별 가능 소지가 있어 legal 검토 대상으로 분류 권장. 의도성은 미입증(당사자는 부인)이므로 '확정 남혐'으로 단정하지 말고 반복성·정황 근거 병기 원칙 유지.
- medium='ad' 판단: 실제 매체는 사내/유튜브 홍보채널 '르노 인사이드'의 신차 홍보영상. 광고와 SNS의 경계에 있으나 형제 항목(GS25)과의 일관성상 'ad' 유지함. 정책상 'sns'가 더 정확하다고 보면 재분류 검토 가능.
- 단일 출처: source_url이 한국일보 1건뿐. 본문 사실(직무정지·조사위·영상삭제·당사자 해명)은 모두 해당 기사로 교차확인됨(SBS/시사저널 등 다수 언론도 동일 보도 확인). 등재 정책상 2차 청정 출처 보강이 필요하면 SBS(news.sbs.co.kr/news/endPage.do?news_id=N1007704952) 추가 가능.

## incident--starbucks-tankday.json
- 사실 확인 방식: 본 사건은 2026-05 발생으로 어시스턴트 학습 컷오프(2026-01) 이후라 훈련 지식으로 검증 불가. WebFetch/WebSearch 실시간 조회로 검증함 — 다수 독립 출처(머니투데이 source_url, MBC imnews 2건)가 사건·사과·문구변경을 확증.
- URL 확인됨: source_url(머니투데이 https://www.mt.co.kr/society/2026/05/20/2026052013381185811) 접근 성공, 기사 제목 '스타벅스 탱크데이 논란 부추기나…AI 합성 콘텐츠 온라인 확산', 2026-05-20자, 행사 중단·정용진 회장 사과·손정현 대표 경질 확인.
- '대표 경질'(title·_comment) 사실성: source_url(머니투데이)과 검색 요약(손정현 스타벅스코리아 대표이사 해임)에서 확증되나, 교차 확인한 MBC imnews 1차 기사(6823442)에는 해임 명시 없음. 단정은 유지 가능하나 사람 검수 시 2차 출처(예: 뉴시스) 보강 권장.
- '탱크데이' 성격 규정 적절: 기사들도 '탱크데이'를 기존 일베 은어로 단정하지 않음. _comment가 '단일 용어가 아닌 날짜+행사명+문구 조합 incident'로 보수적으로 규명한 것은 출처와 정합. related_surface='탱크데이'는 단순 표면 연결로만 사용 — 향후 골든 엔트리화 시 '탱크데이' 자체를 독립 혐오어로 등재하지 않도록 주의.
- 라이선스: incidentPayload 스키마에 license_note 필드 없음(뉴스 출처라 사실 추출만). _comment 주석의 '청정 출처: 머니투데이·뉴시스. 나무위키 미사용'은 정확. namu.wiki는 source_url에 미사용(검색 결과에만 등장).
- 스키마상 incidentPayload는 단일 source_url 평면 구조 — 별도 evidence 배열/excerpt/evidence_type/severity/categories/negative_examples 필드가 없음. 따라서 해당 검증 단계(라이선스 evidence별 표기·excerpt 300자·misandry 청정 evidence 강제 등)는 본 파일 구조에 비적용.

## new_marker--jipge-songarak.json
- misandry 카테고리 표식: 정책상 '의도성 미입증·반론 병기' 원칙을 origin_note와 _comment에서 준수하고 있음을 확인. 검출 운용 시 '단일 손 모양만으로 자동 단정 금지' 메모가 반드시 마커 정책에 반영되어야 함(과잉 색출=괴롭힘 리스크). 사람 검수자가 최종 release 전 재확인 권장.
- origin_note가 637자로 길고 4개 incident(GS25 2021 / 메이플스토리 2023-11-25 / 르노코리아 2024-06-30 등)를 요약 포함. 8개 핵심 사실 전부 출처 위키백과 '집게손가락 음모론' 문서에서 명시적으로 확인됨(연도·날짜 일치). 다만 서술이 중립적 사실 추출 톤인지(서사화가 아닌지) 사람 검수 권장.
- 이미지 미첨부 정책 메모 확인: 표식 이미지 자체는 license_note에 따라 미첨부, 존재·맥락·출처 메모만 기록. M4 이미지 단계 진입 시 이미지 라이선스(위키미디어 명시본 등) 별도 확보 필요.

## new_term--503-number.json
- [중대/법무] '503'을 사용하는 정치 진영 귀속이 출처마다 엇갈림. 원본은 '보수·극우' 사용으로 단정했으나, 인용된 두 출처(뉴시스·한국부동산뉴스)는 오히려 박 전 대통령 수감을 상징하는 '진보·비판 진영의 멸칭/조롱 코드'로 소개함. 본 검증에서 중립 기술로 수정했으나, 프로젝트의 정치적 비대칭 민감성을 고려해 사람이 1차 출처로 사용 진영을 확정할 것.
- [법무] surface가 실존 전직 대통령(박근혜)의 수인번호로 특정인 실명·신상과 직결됨. legal_review_flag=true 유지 적절. 명예훼손/모욕 리스크 검토 필요.
- evidence_type가 두 건 모두 'definition'으로 표기됨. 두 기사는 본질적으로 2026-05 스타벅스 탱크데이 '사건' 보도(incident 성격)이며 그 안에서 503의 의미를 해설하는 구조임. 인용된 excerpt 기준으로 definition도 방어 가능하나, incident로 보는 것이 더 정확할 수 있어 큐레이터 판단 권장.
- 두 출처 모두 2026-05 단일 사건(탱크데이)에 집중되어 있어, '503' 도그휘슬 용법의 일반성·지속성을 입증하기엔 출처 다양성이 부족함. 단일 사건 외 별도 용례 출처 보강 권장.

## new_term--doenjangnyeo.json
- evidence URL 2건 모두 WebFetch로 본문이 '된장녀' 용어와 일치함을 확인했고 정의·유래·여성혐오 멸칭 성격이 출처와 부합. namu.wiki 출처 없음.
- archive_url 2건(web.archive.org/web/2024/...)은 형식만 점검했고 실제 스냅샷 라이브 접근은 미검증 — 사람 검수 시 아카이브 유효성 한 번 확인 권장.
- origin_period가 '2006년경'이나 위키백과는 확산 가속 계기로 2005년 주간경향 기사를 들고, 페미위키는 '2006년부터 크게 유행'으로 서술. 2005(징후)~2006(본격 유행)로 보면 모순은 아니나 표기상 '2005~2006년경'이 더 정확할 수 있음.
- severity=4는 출처가 직접 강도를 명시하지 않으므로 평가자 재량 판단치 — 사람 검수 시 다른 여성혐오 멸칭과의 일관성 확인 권장.

## new_term--eung-di.json
- origin_period 정밀도: 교차검증(웹검색)상 노무현 '응디/응딩이' 밈은 민주평통 제50차 상임위 연설('미국 응딩이 뒤에서 숨어가지고' 발언)을 근거로 2007년경부터 밈화된 것으로 보임. 청정 cite 출처(페미위키)는 '민주평통 발언 유래'만 확인하고 정확한 연도는 명시하지 않음. 정확한 최초 유래 연도(2007 vs 2014)는 청정 출처로 추가 확정 권장(현재 origin_period는 응디시티 유포 기준으로 표기).
- 두 evidence URL(스포츠경향 2018-01-25 기사, 페미위키 응디 문서) 모두 WebFetch로 접근·내용 일치 확인됨. archive_url(웹 백업)이 두 evidence 모두 누락 — 스키마상 위키/뉴스는 archive_url 필수 권장이므로 적재 전 web.archive.org 백업 URL 보강 권장.
- legal_review_flag=true 적정(실명·고인 비하). categories=deceased/politics/community_jargon로 misandry 비대칭 규칙 비해당. severity=5는 비하 의도 명확 사례로 타당하나, ambiguity=ambiguous(엉덩이 방언 동음이의)와의 조합상 검출 로직에서 safe_contexts 우선 적용이 반드시 필요 — negative_examples 3건이 must_pass로 보호되는지 골든셋 단계에서 재확인 권장.

## new_term--gunmusae.json
- 어원 출처 불일치(인적 검수 권장): meaning/origin_story는 '군대+앵무새'라고 단정하나, 정의 출처인 페미위키 본문은 '군인(soldier)+앵무새'라고 명시함('군무새는 군인 + 앵무새의 합성어'). insight.co.kr 본문은 '군대와 앵무새의 합성어'로 표기해 두 출처가 충돌. 두 표기 모두 출처가 있어 needs_verification은 강제하지 않았으나, 등재 시 '군인/군대' 중 어느 표기를 정본으로 할지 결정 필요. 참고로 페미위키 evidence excerpt에는 어원이 빠져 있고 사용 의미만 인용돼 있어, '군대+앵무새' 주장의 직접 근거는 신뢰도 3짜리 insight.co.kr 1건뿐임.
- insight.co.kr(news/336442) evidence의 evidence_type='origin'은 경계선: 기사 본문 자체는 GS25 포스터 의혹(=incident)이 주제이고 어원 설명은 부수적임. 선택된 excerpt('군대와 앵무새의 합성어로 여초 카페에서 만들어 낸 비하 단어')는 origin 성격이 맞아 그대로 두었으나, 동일 기사가 related_incidents(GS25 의혹)에서도 출처로 재사용되고 있어 단일 incident 기사를 origin 근거로도 겸용하는 구조임. misandry 카테고리의 '청정 origin' 근거가 사실상 이 1건에 의존하므로, 가능하면 더 명확한 사전/정의성 origin 출처 보강 권장.
- insight.co.kr 신뢰도 reliability=3은 매체 성격(연성·논란 위주 매체) 대비 다소 후한 편. 범위(1~5) 내라 수정하지 않았으나 인적 검수 시 하향 검토 여지 있음.
- archive_url(web.archive.org/...336442)은 환경 제약으로 직접 확인 불가했음(WebFetch가 web.archive.org 차단). 대신 라이브 URL(insight.co.kr/news/336442)로 본문·발행일(2021-05-02)·인용문 일치 확인 완료. 아카이브 링크 자체의 유효성은 미확인.

## new_term--hannam.json
- 경향신문(khan.co.kr) evidence의 excerpt는 직접 인용이 아니라 의역/종합임: 실제 기사는 '한남충(한국남자+蟲)'(씹치남 항목 부연)과 '미러링'을 각각 별도 용어풀이로 설명함. 사실관계는 정확하나 따옴표 직접 인용으로 오해되지 않도록 검수 권장.
- origin_story의 '메르스 갤러리 파생', '김치녀 등 여성 비하어 대응' 세부 서술은 널리 알려진 사실이나 인용된 2개 출처 excerpt에는 직접 포함되어 있지 않음(위키백과는 2015년 8월/메갈리아/미러링까지만 명시). 보수적 검수 시 해당 세부에 청정 출처 추가 권장.
- archive_url 2건(web.archive.org) 미확인: 실행 환경에서 web.archive.org 접근이 차단되어 아카이브 보존 여부를 확인하지 못함. 라이브 URL 2건은 모두 정상 접근·내용 일치 확인됨.
- spread_communities 항목이 식별자가 아닌 서술형 문자열('megalia(발원)','래디컬 페미니즘 계열 커뮤니티로 확산')임. 스키마상 자유 문자열이라 통과하나, 후속 정규화 단계에서 식별자 분리 필요할 수 있음.
- payload에 collector 필드가 최상위와 payload 내부에 중복 존재(둘 다 'agent:lexicon-researcher'). 값은 일치하나 적재 시 단일화 검토 권장.

## new_term--heobeo-heobeo.json
- misandry 분류의 근거는 '미입증 주장'에 기반함: 허버허버는 본래 음식 급히 먹는 의태어이며, 남성 비하 의도는 출처(한국일보·뉴시스)와 항목 origin_story 모두 '의도성 미입증'으로 명시. 항목은 ambiguity=common + combination_rules(트리거 동반어) 게이트로 보수적으로 처리했으나, misandry 라벨을 disputed 용어에 부여하는 것이 의도된 정책 결과인지 사람 검수 확인 필요.
- evidence는 전부 news 출처(한국일보 origin, 뉴시스 definition)이며 위키·커뮤니티 청정 출처는 없음. 스키마/정책상 news로 origin·definition 충족은 허용되나, '청정 origin/definition'을 위키성 1차 출처로 보강할지 검토 권장.
- related_incidents의 insight.co.kr URL(기안84 나혼자산다 자막 논란)은 WebFetch로 주제 일치 확인됨(evidence 아님, source_url로만 사용). related_incidents 날짜('2021-02', '2021-03-15')는 기사 게재일과 정합적이나 정확한 일자는 미세 확인 권장.
- URL 3건(hankookilbo, newsis, insight) 모두 WebFetch 접근·주제 일치 확인. web.archive.org는 본 환경에서 fetch 불가로 아카이브 자체 내용 직접 확인은 불가했으나, 도메인 불일치만으로 제거 근거 충분.

## new_term--hongeo.json
- 라이선스 표기 일관성(경미): KCI 학술논문 evidence의 license가 '언론사 저작권(사실 추출만)'으로 되어 있음. 엄밀히는 학술지/출판사 저작권이 정확하나, 동일 출처를 쓰는 형제 파일 new_term--jeolladian.json과 표기가 일치하므로 단독 수정하지 않고 플래그만 남김. CC BY-SA로 잘못 표기된 것은 아니며(중대 오류 아님), academic 출처 전반의 라이선스 라벨 통일은 사람 검수에서 일괄 결정 권장.
- published_at 확인: HuffPost evidence의 published_at='2026'은 명시적 게재일을 WebFetch로 단정하지 못했으나, 본문이 2026-05 H홈쇼핑 사고와 6·3 선거 맥락을 다루는 동시대 기사로 확인되어 연도 모순 없음. 정확한 일자(YYYY-MM-DD)는 사람 검수 시 보강 권장.
- 전 evidence URL 3건 및 related_incident URL 1건 모두 WebFetch로 접근·내용 일치 확인됨(미확인 URL 없음). KCI 인용 수치(78.76%/4,538건), 위키백과 라이선스(CC BY-SA 4.0), 홍어/전라디언 비하어 서술 모두 출처와 일치.

## new_term--jeolladian.json
- origin_period/origin_story의 '2006년경 등장, 포털 뉴스 댓글에서 전라디안 형태로 시작' 및 '2010년대 일베 고착' 주장은 인용된 3개 evidence(KCI 양혜승 2022 / 아시아경제 2019 / 위키백과 일베저장소) 어디에도 직접 근거가 없는 재구성 서술임. 용어의 실재성·의미·전라도 비하어 분류·2019 일베 귀속은 학술+위키 definition evidence로 견고히 입증되므로 needs_verification까지는 불필요하나, 구체적 등장 연도(2006)와 '전라디안' 선행표기 주장은 별도 1차 출처 확인 필요.
- URL 4건(KCI 학술, 아시아경제, 위키백과 일베저장소, 한국일보 related_incident) 모두 WebFetch로 접근·내용 일치 확인 완료. KCI는 제목/저자(양혜승)/학술지(지역과 커뮤니케이션 26(2), 36-70)/발행연도(2022)/초록 인용문('홍어','홍어족','전라디언','깽깽이')까지 정확히 일치.
- license 표기 컨벤션 일관성 참고: 동일 KCI 논문을 인용하는 형제 파일 new_term--hongeo.json의 evidence[0]도 academic source인데 '언론사 저작권(사실 추출만)'으로 동일하게 잘못 표기되어 있음 — 본 파일과 동일 교정 권장(이번 작업 범위 밖이라 미수정).

## new_term--jwajom.json
- origin_story 미검증: 단일 evidence(2013 한겨레 '고전중독' 칼럼)는 좌좀/우좀을 비인간화·증오 표현으로 '규정/비판'하는 definition 출처일 뿐, '2008년 촛불집회 전후 발생' 및 '좌파 좀비→좌좀 축약'이라는 유래/시기 주장은 이 출처가 직접 뒷받침하지 않음. 파일이 '회자되며'로 헷지했고 needs_verification=false이지만, origin_story/origin_period는 사실상 무출처이므로 사람 검수에서 별도 origin evidence 확보 또는 유래 서술 톤다운 검토 권장.
- archive_url 부재: 유일 evidence가 news.nate.com 재수록본인데 archive_url(web.archive.org 백업)이 없음. 네이트 뉴스 페이지는 만료/삭제 위험이 있어 스키마도 뉴스/위키에 archive_url을 권장함. 단일 출처 항목이므로 백업 URL 1건 추가 권장(검증되지 않은 archive URL을 임의 생성하지 않기 위해 본 검증에서는 추가하지 않음).
- WebFetch 노이즈 확인됨(실제 불일치 아님): 1차 WebFetch가 필자를 '이준형'으로 보고했으나, WebSearch로 정식 제목 '[이상수의 고전중독] 좌좀/우좀과 행시주육' + 동일 URL + 필자 이상수(전 한겨레 기자) + 발행 2013-05-27 + 매체 한겨레가 교차 확인됨. evidence는 진본이며 제목/URL/license/published_at/publisher 모두 일치. '이준형'은 소형 모델의 사이드바/오인식 산출물로 판단되어 무시함.
- meaning 표기 차이(경미): 파일은 '좌파 좀비'로 풀이, 일부 사전(위키낱말)은 '좌익 좀비'로 풀이. 둘 다 통용되며 칼럼/검색 결과와 모순되지 않으므로 수정하지 않음. 참고만.

## new_term--kimchinyeo.json
- 어원 미확정: '김치맨에서 파생', '2010년 이전 김치를 좋아하는 여자/한국 여성의 농담조 호칭으로 무해하게 쓰임' 주장은 청정 출처(위키백과/페미위키/언론)에서 확인 불가, 나무위키에만 기재됨. 이 서술이 ambiguity=ambiguous + safe_contexts(음식 김치)의 핵심 정당화였으므로 사람 검수 필요. 단, 음식 '김치'와의 동음 충돌 자체는 어원과 무관하게 실재하므로 ambiguous 분류·safe_contexts는 유지함.
- needs_verification=true 설정 — draft 고정 상태. 어원 관련 청정 2차 출처(국립국어원/학술 논문/위키백과 등) 확보 시 origin_story 보강 후 해제 검토.
- 페미위키 evidence의 evidence_type을 'origin'으로 유지했으나, 실제 페이지는 어원(etymology)보다 '된장녀 계열 멸칭으로의 정착·사회적 반박'을 다루므로 'definition' 성격이 더 강함 — 사람 검수자가 origin/definition 재분류 판단 권장.
- URL 2건 모두 접근·내용 확인 완료(서울신문=일베 확산 직접 인용 일치, 페미위키=정의/된장녀 계열 서술 + CC BY-SA 4.0 확인). archive_url은 미검증(스냅샷 존재 여부 별도 확인 권장).

## new_term--mamchung.json
- origin_period '2015년경'은 인용된 두 출처(한국일보·페미위키) 어디에도 명시되지 않음 — 통념상 그럴듯하나 evidence로 뒷받침되지 않은 추정치. 사람 검수 시 별도 확인 권장.
- 페미위키가 제시한 기원(백종원 '마이 리틀 텔레비전' 세부 코너)은 일반적으로 알려진 '맘충' 기원 설명과 다소 다를 수 있음 — 단일 위키 출처에만 의존하므로 교차 확인 권장.
- URL 2건 모두 WebFetch 접근·내용 확인 완료(미확인 없음).

## new_term--no-ala.json
- URL 3건 전부 WebFetch 접근·내용 일치 확인됨(위키백과 일베저장소 사건/사고 페이지, 스포츠경향 2013-08-21, 머니투데이 2013-08-20). namu.wiki 출처 없음.
- 사실 검증 완료: 2013-08-20 SBS 8뉴스 '특파원 현장'(일본 수산물 방사능) 코너 자료화면 배경에 노알라 합성물 노출 방송사고 → 머니투데이 본문 인용문으로 직접 확인됨. related_incidents의 '특파원 현장' 디테일 정확.
- 라이선스 표기 정확: 위키백과=CC BY-SA 4.0, 뉴스 2건='언론사 저작권(사실 추출만)'. 정상.
- minor) 머니투데이 evidence_type='origin'은 다소 부정확 — 실제로는 스포츠경향과 동일한 2013 SBS 방송사고를 다룬 incident성 보도. excerpt가 이미지의 제작·유포 목적을 설명하므로 'origin'도 방어 가능하나 'incident'가 더 정확. 차단 사유 아님.
- minor) 머니투데이 evidence에 archive_url 누락(스키마상 뉴스는 '필수 권장'). 적재 전 web.archive.org 백업 URL 보강 권장.
- 참고: 더 직접적인 정의 출처로 한국어 위키백과 전용 문서 '노알라'(https://ko.wikipedia.org/wiki/노알라)가 존재하나 disambiguation 성격. 현재 인용한 '일베저장소의 사건 및 사고' 페이지가 정의 인용문을 더 명확히 포함하므로 교체는 선택사항.

## new_term--no-ending-pattern.json
- meaning/origin_story의 '평서문(declarative)에 노를 붙이는 것이 일베 말투 특징'이라는 핵심 단정은 두 뉴스 출처 어디에도 '평서문' 표현으로 등장하지 않음. 엑스포츠뉴스는 오히려 '경상도 사투리와 다르다는 지적도 있으나 실제로 쓰는 표현이라는 주장도 있었다'고 양쪽을 병기. 추가한 위키백과는 -노=의문사의문/-나=판정의문 구분만 입증할 뿐 '일베가 평서문에 노를 붙인다'는 부분은 직접 입증하지 않음. 즉 평서문 프레이밍은 일부 편집적 합성. 핵심 사실(일베 사용·노무현 비하·EBS 들켰노 사건)은 출처로 견고해 needs_verification까지는 불요하나 문구 강도는 사람 검수 권장.
- combination_rules[1](proximity, window=0)의 trigger_terms_surface(['들켰노','재밌노','꼴좋노','당했노','쌌노'])는 그 자체가 베이스 패턴 (.+)노[.!?…]*$ 에 이미 매칭되는 형태임 — 별도 동시출현 용어가 아니라 패턴 자체의 인스턴스라 proximity 트리거 설계로는 의미상 어색함. 적재 시 규칙 의미 재검토 필요.
- legal_review_flag=false이나 categories에 deceased 포함 + combination_rules에 실명 '노무현'·'근혜' 트리거가 들어가고 고인(노무현 전 대통령) 비하 맥락임. 프로젝트 메모리상 고인 비하 법적 민감도가 높아 legal_review_flag=true 검토 권장(서술이 자문/기술적 성격이라 강제 수정은 보류).
- 두 뉴스 기사 published_at=2025-11-06이고 EBS 영상 공개일은 '지난달 25일'(=2025-10-25)로 기사 본문과 정합. 위키백과 evidence에는 archive_url 미첨부 — 스키마상 위키/뉴스 archive_url '권장'이므로 적재 전 web.archive.org 백업 권장.

## new_term--nomu.json
- combination_rules co_occurrence trigger에 '노무한'이 포함되어 있으나 '노무한'은 base '노무'를 부분문자열로 포함하는 파생형이라 동시출현 트리거로서 토크나이저 의존적이고 논리적으로 부정확할 수 있음 — 적재 시 변형/패턴 규칙으로 재분류 검토 필요
- trigger_terms 운지/응디/노알라는 독립 검증 결과 실제 일베 노무현 비하 용어가 맞으나(한국어 위키백과·페미위키·언론 확인), 본 파일의 trigger_evidence 3개 URL은 박수/핑계/노무한 용법만 직접 입증함 — 운지/응디/노알라 가산 규칙은 직접 근거가 없으니 별도 evidence 보강 권장
- legal_review_flag=true 정상 (실명 노무현 전 대통령 관련) — 적재 전 법무 사인오프 필요
- URL 3건 모두 WebFetch 접근·내용 일치 확인 완료, namu.wiki 출처 없음

## new_term--ojo-oeok.json
- evidence_type=definition인 뉴시스 항목은 엄밀히는 '논란 보도(incident 성격)'에 가까움. definition으로 둬도 결정적 결함은 아니나, 청정 '의미 정의' 단독 출처가 뉴스 논란 기사뿐이라는 점은 misandry 카테고리 등재 시 사람 검수가 필요
- 핵심 의미('남성 정자 오조오억 개' 비하)는 합의된 사실이 아니라 '남초에서 제기된 주장'이며, 3개 출처 모두 '비하 의도 없는 단순 과장 수사'라는 강한 반론을 병기함. severity=3 + misandry 태그 부여는 프로젝트 메모의 남혐 비대칭 민감성을 고려해 사람이 최종 판단 권장. meaning/origin_story에 의도성 미입증은 명시되어 있음
- 한국일보 evidence published_at='2021-04-21' — URL 슬러그(A2021042110280003760)는 04-21을, 페이지 표시 날짜는 04-22를 가리켜 날짜가 불일치. 초기 게재 vs 수정일 추정이라 보수적으로 미수정. 사람 확인 권장
- URL 3건(뉴시스/위키트리/한국일보) 모두 WebFetch 접근 성공·내용 일치 확인됨. 위키트리만 archive_url 존재, 뉴시스·한국일보는 archive_url 없음(스키마상 권장 사항이라 통과)

## new_term--ottoke.json
- 미확인 URL(아카이브): web.archive.org가 이 환경에서 차단되어 3개 evidence의 archive_url 접근성을 확인하지 못함 — https://web.archive.org/web/2024/https://www.hankookilbo.com/News/Read/A2022021514300002379 , https://web.archive.org/web/2024/https://www.khan.co.kr/opinion/yeojeok/article/202202152122005 , https://web.archive.org/web/2024/https://www.seoul.co.kr/news/newsView.php?id=20210418500025 (원문 3개 모두 WebFetch로 실재·내용 일치 확인됨, 아카이브 스냅샷만 미검증)
- 남초 커뮤니티 발원 시점·경위(통상 2018 디시 거론)는 청정(비-나무위키) 출처로 확정하지 못함. 본문에서는 단정을 제거하고 '미확정'으로 표기했으나, 청정 origin 출처를 추가 확보하면 origin_story/origin_period 보강 권장
- 검색 단계에서 나무위키 URL이 다수 노출되었으나 evidence로는 일절 채택하지 않음(법무 정책 준수). 사람 검수 시 나무위키 유래서술이 본문에 재유입되지 않도록 주의
- GS25 사건 연도: 청정 출처상 2021년 4월로 확정(서울신문). 한국일보 원문은 '지난해'로만 표기하므로 연도는 서울신문 근거로 명시함 — 정합 확인됨

## new_term--samilhan.json
- 사실성 전수 확인 완료: 3개 evidence URL 모두 WebFetch로 접근 성공 + 용어/사건 일치. 서울신문(2015-07-16, definition): '삼일한=여자는 3일에 한 번 때려야' 일베 유래 여성비하어로 정의·분석 — 일치. 머니투데이(2014-10-08, incident): 서울대 관악게임리그 '삼일한' 팀명 논란 및 물리천문학부/팀장 사과문 — 일치. 세계일보(2021-08-25, incident): 잡코리아 맞춤법검사기 '삼일한→3일에 한 번 때려야 할 여자' 대치어 노출, 사람인도 동일 문제, 잡코리아 사과·수정 — 일치.
- namu.wiki URL 없음(정책 준수). 라이선스 표기 3건 모두 뉴스 → '언론사 저작권(사실 추출만)' 정확. excerpt 전부 300자 이내. categories ['misogyny','community_jargon'] 모두 enum 내. misandry 아님(단계7 강제규칙 비적용). severity 5는 명시적 신체폭력 정당화 함의로 타당.
- origin_period '2010년대 초'는 코인 시점을 직접 증빙한 출처가 아닌 추정(일베 2010년 개설 + 2014/2015 보도 기반). 보수적으로 needs_verification까지 올릴 정도의 단정은 아니나, 정확한 발생 연도가 중요하면 사람 검수 권장.
- related_incidents[1] occurred_at '2014-09-30'은 '2014년 9월 서울대 축제' 행사를 근사한 값(기사 본문은 '9월'까지만 명시). 정확 일자 미확정.
- 머니투데이 evidence의 archive_url 호스트(news.mt.co.kr/mtview.php?no=...)가 live url 호스트(www.mt.co.kr/society/...)와 다름. 둘 다 동일 기사로 정상 접근되나, 아카이브 스냅샷 URL 형식이 본문 URL과 불일치하는 점 참고.

## new_term--seunsangnim.json
- 청정(비-나무위키) origin/definition 출처 없음: '슨상님'의 김대중·호남 멸칭 의미·유래는 evidence로 입증되지 않았고 _comment상 청정 출처가 나무위키뿐이라 needs_verification=true로 유지됨. 등재 전 학술/언론 유래 정의 추가 확보 필요.
- 프레이밍 긴장: 유일한 evidence(뉴스토마토 2014-05-03, WebFetch로 제목·발행일·내용 일치 확인)는 해당 표현이 '사회통념상 모욕이 아니다'라고 판단한 항소심(벌금 100만→20만 감형) 사건임. meaning/origin_story의 '멸칭' 단정과 결이 달라 법무 검토(legal_review_flag=true 설정됨) 시 양측 서술 균형 재확인 권장.
- 경미: spread_communities에 origin_community와 동일한 'ilbe'가 중복 기재됨(스키마 위반 아님, '발원·확산처 분리 기록' 취지상 정리 고려 가능).
- 특정인(김대중 전 대통령) 실명 연관 항목 — legal_review_flag=true. 등재 전 법무 최종 확인 필요.

## new_term--ung-aeng-ung.json
- origin_period의 트위터 유행 시작 연도(2017~2018)는 인용된 두 뉴스 기사에 구체 연도가 없음 — 별도 1차 출처 없이 일반 통념 기반. 정확 연도 필요 시 추가 검증 권장
- origin_story의 '2021년 기업·방송 사례'는 뉴시스 기사(2021-04-20)에 직접 명시되지 않은 일반 서술 — 구체 사례별 출처 보강 권장
- 뉴시스 기사는 '웅앵웅=남성 말 무시' 해석을 남초 사이트의 주장으로 보도하고, 동시에 이를 남혐으로 프레임화하는 것 자체를 '진화된 여혐'으로 보는 반론도 함께 실음. misandry 분류는 '논란/주장' 성격임을 등재 시 유지할 것(엔트리 본문은 이미 '주장'·'미입증'으로 적절히 헤지함)
- ambiguity=common(일반 의태어로도 널리 쓰임)이므로 단독 매칭 금지·combination_rules 기반 트리거가 운영 단계에서 실제 작동하는지 골든셋(negative_examples 3건 must_pass) 확인 필요

## 리서치 단계에서 제외(skipped)된 대상
- 이마트 '응디시티' 광고 논란(2016) — 검증 실패: 이마트가 '응디시티'를 광고/매장음악에 사용했다는 2016년 보도를 뉴스/위키백과 어디서도 확인 불가. '응디시티'는 2014년경 일베 제작 노무현 합성 음원/영상이며, 언론으로 정착한 '응디' 관련 실사고는 2018년 일베의 뉴욕 타임스퀘어 비하 광고(스포츠경향 보도)임. '응디' 용어 자체는 정상 채택했고, 미검증 이마트 2016 사례는 incident로 만들지 않음(날조 방지).
- 한국민속촌 SNS 일베 용어 사용 논란 — 검증 실패: 한국민속촌(트위터/페이스북) 공식 SNS의 일베 용어 사용 논란 및 사과 보도를 다중 검색에서 전혀 확인하지 못함(검색 결과는 모두 무관한 연예인/구단 사례로 회귀). 사용된 용어를 특정할 1차 출처가 없어 사고 자체가 실재했는지 불명 → 사례 미작성.
- 노무현 합성 박수 짤 '기업 마케팅' 사고 — 부분 검증/재정의: '노무 박수' 자체를 마케팅에 쓴 기업 사례 대신, 실제로 검증된 것은 (1)롯데 자이언츠 공식 유튜브 '노무한 박수' 자막 사고(2026-05, 뉴스1·뉴시스·헤럴드경제·SBS 다중 보도)와 (2)SBS플러스 '왈가닥뷰티' '고 노무 핑계' 자막 사고(2020-06, 경향신문). 둘 다 '노무' 용어 엔트리의 evidence/related_incidents로 반영하고 롯데 사례는 독립 incident 파일로 작성. 별도의 '노무한 박수 짤 마케팅 활용' 기업 사례는 미검증이라 제외.
- 무한도전 일베 합성 이미지/시디즈 광고 표식 사례 — 배치 시작점으로 제시됐으나 이번 검색에서 신뢰 가능한 1차 보도 URL을 직접 확인(WebFetch)하지 못해 날조 금지 원칙상 제외. 별도 news-monitor 패스에서 사실 확인 후 incident/new_marker로 추가 권장.
- 5·18 관련 홍어드립송 등 개별 합성물 — 커뮤니티 자체 서술 외 청정 1차 출처 미확보로 term/marker 단독 등재 보류(홍어 origin_story에 맥락만 요약 반영).
- 없음 — 배정된 5개 대상 모두 청정 출처로 사실 검증되어 작성 완료. 추가 보조 단서로 확인된 namuwiki 문서는 법무 정책에 따라 evidence에 일절 기록하지 않음.
- 보이루 — new_term 미등재: 법원이 2022~2023년 '보이루는 보겸이 만든 여성혐오 용어'라는 윤지선 논문 각주를 허위·명예훼손으로 판단하고 보겸 측 손을 들어줌. 확정 여혐 용어로 등재하면 판결에 배치되므로, 양측 균형 서술의 학술·법적 논란만 incident(related_surface=보이루)로 기록함.
- 숫자 코드 '318': 노무현 비하 코드라는 보도/청정 출처를 확인하지 못함(검색 결과 없음). 날조 방지 위해 제외 — 추가로 확인된 것은 '523'(운지절, 노무현 투신일)이나 이 또한 청정 origin/definition 뉴스 출처를 이번 범위에서 확정하지 못해 미작성.
- 숫자 코드 '1212'(12·12 군사반란)·'0518'(5·18) 단독 항목: 한국일보 도그휘슬 기사에서 언급되나 의미·조합 위험을 단독 용어로 규명할 만큼 구체적 정의 출처가 부족. 503(스타벅스 보도로 수인번호·조합 맥락 명확)만 number 항목으로 채택하고 1212/0518은 보류.
- '탱크데이'를 new_term으로 등재하지 않음: 사실 확인 결과 기존 확립된 일베 은어가 아니라 스타벅스 '탱크 텀블러' 행사명이며, 위험은 '5/18 날짜+책상에 탁 문구' 조합에서 발생 → 단일 용어가 아니라 incident로 규명.

## 배치 요약
- **deceased-ilbe**: 고인비하·일베 용어 4건을 작성·검증 완료(전부 validate_candidates.py 통과, 나무위키 URL 0건). 신규 용어 노알라(노무현+코알라 합성, severity 5, SBS 8뉴스 2013 방송사고로 정착·위키백과 CC BY-SA 근거), 응디(노무현 육성 합성 비하어이나 '엉덩이' 동남방언과 동철 → ambiguous+safe_contexts, 페미위키 유래+타임스퀘어 광고 2018 incident 근거), 노무(노무현 비하 도그휘슬이나 '노무관리·노무사' 등 흔한 일반어 → ambiguity=common, combination_rules 3종+trigger_evidence로 단독 오탐 차단)를 등재했고, 롯데 자이언츠 '노무한 박수' 자막 사고를 독립 incident로 기록했다. 이마트 응디시티(2016)·한국민속촌 SNS 논란은 1차 출처 검증 실패로 날조 없이 skipped 처리했다.
- **jargon-region**: 일베 지역비하 은어 4건(홍어·전라디언·슨상님·좌좀)과 실사고 1건(H홈쇼핑 호남 비하 광고)을 candidate-payload 스키마로 작성, 5개 파일 모두 validate_candidates.py 통과. 출처는 KCI 학술논문(양혜승 2022, 홍어·전라디언 definition), 위키백과 CC BY-SA 4.0, 아시아경제·한국일보·뉴스토마토·한겨레·허프포스트 뉴스로 교차 검증했고 나무위키 URL은 어떤 필드에도 기록하지 않았으며 뉴스 3건은 web.archive.org 백업 URL을 확보했다. 홍어는 음식 동철이라 ambiguous+safe_contexts, 슨상님은 청정 origin/definition 출처가 나무위키뿐이고 2014 법원이 해당 표현을 사회통념상 모욕으로 단정하기 어렵다고 판단한 점을 양측 병기하여 needs_verification=true·legal_review_flag=true로 보수 처리했다.
- **misandry**: 남혐 용어 5건(허버허버·오조오억·웅앵웅·한남·군무새)을 청정 출처(뉴스 + 위키백과/페미위키 CC BY-SA 4.0)로만 사실 검증해 new_term 후보 파일로 작성했고, 5개 모두 candidate-payload 스키마 검증을 통과했다(전체 디렉터리 20/20 통과, surface 중복 없음). 허버허버·오조오억·웅앵웅은 단독으로는 무해한 일반어/수 표현이라 ambiguity=common 또는 term_kind=number로 두고 combination_rules + trigger_evidence를 채웠으며, 한남은 '한남동' 지명 동철 때문에 ambiguous + safe_contexts를 달았다. 모든 항목이 청정 origin/definition evidence를 확보해 needs_verification=false로 정당화되며, 나무위키 URL은 어떤 필드에도 기록하지 않았다.
- **misogyny**: 여혐 용어 6건을 사실 검증 후 작성: new_term 5건(김치녀·된장녀·맘충·삼일한·오또케)과 incident 1건(보이루-윤지선 논문 논란). 모든 항목이 candidate-payload 스키마 검증을 통과했고, 출처는 뉴스(서울신문·세계일보·머니투데이·한국일보)와 CC BY-SA 위키(위키백과·페미위키)로 교차 검증했으며 나무위키 URL은 어떤 필드에도 기록하지 않았다. 동철 충돌이 있는 김치녀·된장녀·오또케·삼일한은 ambiguous로 두고 safe_contexts/negative_examples를 채웠고, 삼일한은 폭력 선동성으로 severity 5, 보이루는 법원이 여혐 용어 규정을 허위로 판단했기에 확정 용어 등재 대신 양측 균형 incident로만 처리했다.
- **markers-codes**: 집게손가락 표식(new_marker 1건, 위키백과 '집게손가락 음모론' 기반으로 의도성 미입증·반론 병기)과 그 연쇄 사례 3건(GS25 2021, 메이플스토리 2023, 르노코리아 2024)을 incident로 분리 작성했고, '~노' 종결어미를 term_kind=pattern·ambiguity=common으로(경상도 방언 오인 방지용 combination_rules+trigger_evidence 포함) 등재하며 EBS '들켰노'(2025-11)를 연관 incident로 추가했다. 스타벅스 '탱크데이'는 사실 확인 결과 단일 용어가 아닌 날짜·문구 조합 사건이라 incident로, 숫자 코드는 보도로 의미·조합이 명확한 '503'(박근혜 수인번호) 1건만 term_kind=number로 작성했다. 모든 출처는 뉴스·CC BY-SA 위키백과만 사용(나무위키 전면 배제)했고 8개 파일 전부 validate_candidates.py 통과, 318/523/1212/0518은 청정 출처 미확인으로 skipped 처리했다.
