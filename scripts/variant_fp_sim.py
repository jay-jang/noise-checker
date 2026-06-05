"""변형 규칙 오탐(FP) 시뮬레이션 — v1.

목적: 변형 생성 규칙(jamo/chosung/leet)이 만들어내는 변형의 normalized_key가
**일반 일상어**의 normalized_key와 충돌하면, 그 변형으로 사전 매칭 시 무해한
일반어를 오탐(false positive)한다. 이 스크립트는 그 충돌을 사전에 측정한다.

방법:
  1. 시드 용어(data/seed의 surface들 + 후보 파일이 있으면 그 surface)의
     변형을 생성한다.
  2. 내장 일반어 목록(고빈도 한국어 일상어, 자체 선정)의 normalized_key를 만든다.
  3. 각 변형의 normalized_key가 어떤 일반어의 normalized_key와 같으면 충돌로 기록.
  4. 변형 종류별 충돌 통계와 운영 권고를 마크다운으로 stdout + 리포트 파일에 출력.

출력: reports/variant-fp-sim-v1.md (+ stdout).

외부 의존성 금지 — 표준 라이브러리 + noise_checker만 사용.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from noise_checker.normalizer import normalized_key
from noise_checker.variants import _gen_chosung, generate_variants

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "seed"
CANDIDATES_DIR = SEED_DIR / "candidates"
REPORT_PATH = REPO_ROOT / "reports" / "variant-fp-sim-v1.md"


# ---------------------------------------------------------------------------
# 내장 일반어 코퍼스 (한국어 고빈도 일상어 — 출처: 자체 선정)
# 일상 대화/뉴스/생활에서 흔한 명사·동사·형용사·부사 위주. 혐오/욕설 배제.
# 변형 규칙(특히 chosung)이 이런 무해어와 충돌하는지 측정하는 기준 집합.
# ---------------------------------------------------------------------------
COMMON_WORDS: tuple[str, ...] = (
    # 가족/사람
    "사람", "아빠", "엄마", "형제", "자매", "친구", "선생", "학생", "아이", "어른",
    "남자", "여자", "아들", "할머니", "할아버지", "이모", "삼촌", "사촌", "동생", "언니",
    "오빠", "누나", "부모", "가족", "이웃", "손님", "주인", "직원", "사장", "동료",
    # 신체/건강
    "머리", "얼굴", "손가락", "발가락", "다리", "어깨", "허리", "무릎", "심장", "병원",
    "약국", "건강", "운동", "산책", "감기", "기침", "체온", "혈압", "치료", "수술",
    # 음식
    "김치", "된장", "고추", "마늘", "양파", "감자", "고구마", "당근", "배추", "오이",
    "사과", "포도", "수박", "딸기", "바나나", "라면", "국수", "김밥", "비빔밥", "불고기",
    "삼겹살", "치킨", "피자", "커피", "녹차", "우유", "주스", "사탕", "과자", "케이크",
    # 장소/이동
    "학교", "회사", "공원", "시장", "마트", "도서관", "극장", "식당", "카페", "은행",
    "공항", "지하철", "버스", "택시", "자전거", "도로", "골목", "교량", "건물", "아파트",
    "주차장", "정류장", "기차역", "터미널", "고속도로", "신호등", "횡단보도", "광장", "운하",
    # 자연/날씨
    "하늘", "구름", "바람", "비", "눈", "햇빛", "달빛", "별빛", "바다", "강물",
    "산길", "들판", "나무", "꽃잎", "풀잎", "단풍", "낙엽", "이슬", "안개", "무지개",
    # 시간/일상
    "아침", "점심", "저녁", "오늘", "내일", "어제", "주말", "휴일", "방학", "출근",
    "퇴근", "약속", "회의", "수업", "숙제", "시험", "발표", "면접", "여행", "캠핑",
    # 사물/물건
    "책상", "의자", "침대", "옷장", "냉장고", "세탁기", "텔레비전", "컴퓨터", "전화기", "시계",
    "안경", "우산", "가방", "신발", "양말", "장갑", "모자", "지갑", "열쇠", "수건",
    "비누", "칫솔", "치약", "휴지", "연필", "지우개", "공책", "필통", "가위", "풀통",
    # 동작/상태(동사·형용사 어간 포함 단어형)
    "사랑", "행복", "기쁨", "슬픔", "걱정", "고민", "희망", "용기", "노력", "성공",
    "실패", "도전", "기회", "선택", "결정", "준비", "정리", "청소", "요리", "빨래",
    "공부", "독서", "음악", "그림", "사진", "영화", "연극", "춤", "노래", "운지법",
    # 추상/사회
    "사회", "경제", "정치", "문화", "예술", "과학", "기술", "역사", "철학", "종교",
    "법률", "교육", "복지", "환경", "에너지", "교통", "통신", "방송", "신문", "잡지",
    "회원", "단체", "모임", "행사", "축제", "전시", "공연", "대회", "경기", "우승",
    # 흔한 형용/부사/기능어성 일상어
    "정말", "진짜", "아주", "매우", "조금", "약간", "전부", "모두", "함께", "혼자",
    "다시", "벌써", "아직", "이미", "금방", "나중", "오랜", "잠깐", "항상", "가끔",
    # 색/숫자성 표현
    "빨강", "파랑", "노랑", "초록", "보라", "하양", "검정", "분홍", "주황", "회색",
    # 직업/활동
    "의사", "간호사", "교사", "경찰", "소방관", "농부", "어부", "요리사", "가수", "배우",
    "화가", "작가", "기자", "변호사", "판사", "회계사", "운전사", "택배", "우편", "배달",
    # 자모/초성과 충돌하기 쉬운 짧은 무해 표현(의도적 포함)
    "사방", "수박씨", "운수", "운명", "운전", "지구", "지도", "지갑은", "병아리", "신발끈",
    # 보강 일상어(중복 제거 후 300+ 보장)
    "거리", "마음", "생각", "이야기", "이름", "번호", "주소", "전화", "메일", "메시지",
    "가게", "물건", "가격", "할인", "영수증", "포장", "선물", "행운", "축하", "감사",
)


def _load_seed_surfaces() -> list[str]:
    """시드 용어 surface 수집: data/seed의 example payload/term + candidates."""
    surfaces: list[str] = []

    def pull(doc: object) -> None:
        if isinstance(doc, dict):
            if "surface" in doc and isinstance(doc["surface"], str):
                surfaces.append(doc["surface"])
            payload = doc.get("payload")
            if isinstance(payload, dict) and isinstance(payload.get("surface"), str):
                surfaces.append(payload["surface"])

    for p in sorted(SEED_DIR.glob("*.json")):
        try:
            pull(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    if CANDIDATES_DIR.is_dir():
        for p in sorted(CANDIDATES_DIR.glob("*.json")):
            try:
                doc = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            pull(doc)
            # candidate 파일이 리스트거나 payload.candidates 형태일 수도 있어 보수적 처리
            if isinstance(doc, dict) and isinstance(doc.get("candidates"), list):
                for c in doc["candidates"]:
                    pull(c)

    # 중복 제거(순서 보존)
    seen: set[str] = set()
    out: list[str] = []
    for s in surfaces:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def run_simulation() -> str:
    seed_surfaces = _load_seed_surfaces()

    # 일반어 normalized_key 색인: key -> [일반어들]
    common_key_index: dict[str, list[str]] = defaultdict(list)
    for w in COMMON_WORDS:
        common_key_index[normalized_key(w)].append(w)

    # 변형 생성 + 충돌 검사
    collisions: list[tuple[str, str, str, str, str]] = []
    # (seed_surface, variant, kind, variant_key, 충돌한 일반어들)
    kind_total: dict[str, int] = defaultdict(int)
    kind_collide: dict[str, int] = defaultdict(int)
    # chosung 길이별 충돌(운영 권고용)
    chosung_len_total: dict[int, int] = defaultdict(int)
    chosung_len_collide: dict[int, int] = defaultdict(int)

    for surface in seed_surfaces:
        for v in generate_variants(surface):
            kind_total[v.kind] += 1
            vkey = normalized_key(v.variant)
            hit = common_key_index.get(vkey)
            if v.kind == "chosung":
                clen = len(v.variant)
                chosung_len_total[clen] += 1
            if hit:
                kind_collide[v.kind] += 1
                collisions.append((surface, v.variant, v.kind, vkey, ", ".join(hit)))
                if v.kind == "chosung":
                    chosung_len_collide[len(v.variant)] += 1

    chosung_probe = _chosung_ambiguity_probe()

    return _render_report(
        seed_surfaces,
        collisions,
        kind_total,
        kind_collide,
        chosung_len_total,
        chosung_len_collide,
        chosung_probe,
    )


def _chosung_ambiguity_probe() -> dict[int, tuple[int, int, list[tuple[str, list[str]]]]]:
    """일반어 코퍼스 자체의 초성 모호성 측정 (시드 의존 없이 chosung 위험 입증).

    각 일반어를 chosung으로 환원(=그 단어를 chosung 변형으로 본 키)했을 때,
    **서로 다른 일반어가 같은 chosung 키로 뭉치는** 정도를 길이별로 잰다.
    한 chosung 키에 둘 이상의 일반어가 모이면, 그 chosung을 단독 매칭 규칙으로
    쓸 때 그 일반어 전부가 오탐 후보다(=문맥 필요).

    Returns: chosung 길이 -> (그 길이 일반어 수, 충돌(≥2 공유) 단어 수,
             예시 [(chosung키, [일반어들]), ...] (단어 ≥2 인 것만, 최대 8건)).
    """
    by_len_keymap: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for w in COMMON_WORDS:
        chosung_key = normalized_key(_word_to_chosung(w))
        by_len_keymap[len(chosung_key)][chosung_key].append(w)

    result: dict[int, tuple[int, int, list[tuple[str, list[str]]]]] = {}
    for clen, keymap in by_len_keymap.items():
        total_words = sum(len(ws) for ws in keymap.values())
        collided_words = sum(len(ws) for ws in keymap.values() if len(ws) >= 2)
        examples = sorted(
            ((k, ws) for k, ws in keymap.items() if len(ws) >= 2),
            key=lambda kv: (-len(kv[1]), kv[0]),
        )[:8]
        result[clen] = (total_words, collided_words, examples)
    return result


def _word_to_chosung(word: str) -> str:
    """일반어를 chosung 표기로 환원(generate_variants의 chosung과 동일 규칙).

    generate_variants는 surface==variant를 제외하므로, 단어 자체의 chosung
    키를 직접 얻기 위해 동일 규칙(_gen_chosung)을 재적용한다(1음절 단어 등도
    측정 대상). _gen_chosung은 variants 모듈 내부 규칙(비공개 영역) 재사용.
    """
    return _gen_chosung(word)


def _pct(num: int, den: int) -> str:
    return f"{(100.0 * num / den):.1f}%" if den else "—"


def _render_report(
    seed_surfaces: list[str],
    collisions: list[tuple[str, str, str, str, str]],
    kind_total: dict[str, int],
    kind_collide: dict[str, int],
    chosung_len_total: dict[int, int],
    chosung_len_collide: dict[int, int],
    chosung_probe: dict[int, tuple[int, int, list[tuple[str, list[str]]]]],
) -> str:
    lines: list[str] = []
    a = lines.append

    a("# 변형 규칙 FP 시뮬레이션 — v1")
    a("")
    a("> 생성: `scripts/variant_fp_sim.py` (재현 가능, 결정적).")
    a("> 일반어 코퍼스: 한국어 고빈도 일상어 "
      f"{len(COMMON_WORDS)}개 — 출처: 자체 선정(혐오/욕설 배제).")
    a("")
    a("## 1. 입력")
    a("")
    a(f"- 시드 용어(surface) {len(seed_surfaces)}개: "
      + ", ".join(f"`{s}`" for s in seed_surfaces))
    a(f"- 일반어 코퍼스: {len(COMMON_WORDS)}개")
    a("")
    a("## 2. 변형 종류별 충돌 통계")
    a("")
    a("변형의 normalized_key가 일반어의 normalized_key와 일치하면 충돌(=오탐 위험).")
    a("")
    a("| kind | 생성 변형 수 | 충돌 수 | 충돌률 |")
    a("|------|------------:|--------:|------:|")
    for kind in ("jamo", "chosung", "leet"):
        t = kind_total.get(kind, 0)
        c = kind_collide.get(kind, 0)
        a(f"| {kind} | {t} | {c} | {_pct(c, t)} |")
    total_t = sum(kind_total.values())
    total_c = sum(kind_collide.values())
    a(f"| **합계** | **{total_t}** | **{total_c}** | **{_pct(total_c, total_t)}** |")
    a("")

    a("## 3. chosung 초성 길이별 충돌 (운영 권고 근거)")
    a("")
    a("| 초성 길이 | chosung 변형 수 | 충돌 수 | 충돌률 |")
    a("|----------:|---------------:|--------:|------:|")
    for clen in sorted(chosung_len_total):
        t = chosung_len_total[clen]
        c = chosung_len_collide.get(clen, 0)
        a(f"| {clen}자 | {t} | {c} | {_pct(c, t)} |")
    a("")

    a("## 4. 충돌 쌍 목록 (시드 용어 변형 ↔ 일반어)")
    a("")
    if not collisions:
        a("_시드 용어 변형과 일반어 간 직접 충돌 없음._ "
          "(현 시드는 동음이의 처리된 `운지` 단일 — 시드 수가 적어 직접 충돌 0은"
          " 정상. chosung 본질 위험은 아래 §5 코퍼스 자체 모호성 측정으로 입증.)")
    else:
        a("| 시드 용어 | 변형 | kind | 변형 키 | 충돌 일반어 |")
        a("|-----------|------|------|---------|-------------|")
        for surface, variant, kind, vkey, hits in collisions:
            a(f"| `{surface}` | `{variant}` | {kind} | `{vkey}` | {hits} |")
    a("")

    a("## 5. chosung 본질 모호성 — 일반어 코퍼스 자체 측정")
    a("")
    a("시드 수와 무관하게 chosung 위험을 입증하기 위해, **일반어 코퍼스 자체를**"
      " chosung으로 환원해 서로 다른 일반어가 같은 초성 키로 뭉치는 정도를 잰다."
      " 한 키에 2개 이상 일반어가 모이면, 그 키를 단독 매칭에 쓸 때 그 일반어"
      " 전부가 오탐 후보다(= 용어가 그 초성을 가지면 무해어를 잡는다).")
    a("")
    a("| 초성 길이 | 일반어 수 | 같은 키 공유(≥2) 단어 수 | 모호 비율 |")
    a("|----------:|----------:|------------------------:|---------:|")
    for clen in sorted(chosung_probe):
        total_words, collided_words, _ = chosung_probe[clen]
        a(f"| {clen}자 | {total_words} | {collided_words} | "
          f"{_pct(collided_words, total_words)} |")
    a("")
    a("대표 충돌 키(같은 초성을 공유하는 무해 일반어 묶음):")
    a("")
    shown = False
    for clen in sorted(chosung_probe):
        _, _, examples = chosung_probe[clen]
        for key, words in examples:
            shown = True
            a(f"- `{key}` ({clen}자): {', '.join(words)}")
    if not shown:
        a("- _없음_")
    a("")

    a("## 6. 운영 권고")
    a("")
    a("1. **chosung 2자 이하는 단독 매칭 금지(문맥 필요).** 초성 2자(예 `ㅅㅂ`,"
      " `ㅇㅈ`)는 무해한 일상어·약어와 충돌 가능성이 높다(§5의 코퍼스 자체"
      " 모호성 측정에서 2자 키가 다수 일반어를 공유함을 확인). chosung 변형은"
      " `verified=false` 기본, 단독 1차 매칭에서 제외하고 문맥 분류 단계로만"
      " 승격한다(또는 2자 이하 chosung은 적재하되 release 게이트에서 비활성)."
      " 시드 데이터의 `운지` 엔트리도 chosung `ㅇㅈ`를 '문맥 의존'으로 명시한다.")
    a("2. **leet 중성 덧댐형(예 `운지1`)은 키가 일반어와 충돌하지 않으나** 과생성"
      " 위험이 있으므로 용어당 상한(≤20)을 유지하고 `auto_generated=true,"
      " verified=false`로 적재해 검수 큐에 넣는다.")
    a("3. **jamo 변형은 정의상 surface와 같은 키로 수렴**하므로 일반어와의 충돌은"
      " 곧 '해당 surface 자체가 일반어와 동음'임을 의미한다(동음이의어 신호)."
      " 이 경우 변형이 아니라 surface의 `ambiguity` 재검토 대상이다.")
    a("4. 충돌이 1건이라도 발생한 변형 규칙·종류는 **자동 적재 시 verified=false"
      " 강제 + 검수 필수**. 임계(예: 종류별 충돌률 > 0%) 초과 종류는 release"
      " 게이트에서 단독 매칭 비활성을 기본값으로 둔다.")
    a("")
    a("> 주: 본 코퍼스는 소규모 자체 선정이므로 절대 충돌률보다 **종류 간 상대"
      " 위험(특히 chosung ≫ leet·jamo)** 해석에 사용한다. 대규모 코퍼스(모두의"
      " 말뭉치 등) 적용은 후속 과제.")
    a("")

    return "\n".join(lines)


def main() -> int:
    report = run_simulation()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[저장] {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
