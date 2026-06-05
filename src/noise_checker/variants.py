"""변형 표기 생성 규칙 엔진 (M1 B2).

docs/02-database-design.md §3.4(term_variant variant_kind enum),
docs/06-test-plan.md §2.1(생성↔매칭 왕복),
docs/01-research-report.md §3(변형 유형 근거 — KOTOX 음운/도상 규칙)을 구현한다.

용어 표면형(surface) 하나에서 위험 변형 후보를 **규칙으로 일괄 생성**한다
(용어별 수작업 나열 금지). 생성 결과는 결정적이다 — 같은 입력은 항상
같은 순서·같은 집합을 돌려준다.

정규화 정합:
  - jamo 변형은 정규화로 surface와 **같은 키로 수렴**해야 한다
    (normalizer가 음절을 호환 자모로 분해하므로 자모분리 표기는 자연히 수렴).
    이 수렴이 1차 매칭(AC)의 전제다.
  - leet/chosung 변형은 surface와 키가 다르므로 term_variant 행으로 따로
    적재되어 자기 자신의 normalized_key로 매칭된다(수렴 불요).

외부 의존성 금지 — 표준 라이브러리 + noise_checker.normalizer만 사용.
"""

from __future__ import annotations

from dataclasses import dataclass

from noise_checker.normalizer import normalized_key

__all__ = ["Variant", "generate_variants", "LEET_MAX_VARIANTS"]


# --- 한글 음절 산술 상수 (U+AC00 = '가') -------------------------------------
_SYLLABLE_START = 0xAC00
_SYLLABLE_END = 0xD7A3
_JUNG_COUNT = 21
_JONG_COUNT = 28  # 받침 없음(0) 포함

# 초성/중성/종성 인덱스 → 호환 자모(U+3131~). normalizer의 분해 결과와 동일한
# 호환 자모를 쓰기 위해, 빈 음절을 합성해 normalizer 경로로 자모를 얻는다.


def _compat_jamo_tables() -> tuple[list[str], list[str], list[str]]:
    """초성(19)/중성(21)/종성(27, 0=없음 제외) 인덱스별 호환 자모 표.

    normalizer와 **동일한** 호환 자모로 수렴시키기 위해, 각 자모만 가진
    음절을 합성한 뒤 normalized_key로 분해해 호환 자모를 역추출한다.
    (예: 초성 i만 가진 'i가 0'번째 음절 = chr(0xAC00 + i*21*28)을 분해하면
    그 초성의 호환 자모가 첫 코드포인트로 나온다.)
    """
    cho: list[str] = []
    for ci in range(19):
        syll = chr(_SYLLABLE_START + ci * _JUNG_COUNT * _JONG_COUNT)
        cho.append(normalized_key(syll)[0])

    jung: list[str] = []
    for vi in range(_JUNG_COUNT):
        syll = chr(_SYLLABLE_START + vi * _JONG_COUNT)  # 초성 ㄱ(0) + 중성 vi
        jung.append(normalized_key(syll)[1])  # [0]=초성ㄱ, [1]=중성

    jong: list[str] = [""]  # 인덱스 0 = 받침 없음
    for ti in range(1, _JONG_COUNT):
        syll = chr(_SYLLABLE_START + ti)  # 초성ㄱ + 중성ㅏ + 종성 ti
        # 분해: [초성ㄱ, 중성ㅏ, 종성...] — 종성은 마지막
        jong.append(normalized_key(syll)[-1])
    return cho, jung, jong


_CHO, _JUNG, _JONG = _compat_jamo_tables()


def _decompose_syllable(ch: str) -> tuple[int, int, int] | None:
    """음절 → (초성 idx, 중성 idx, 종성 idx). 음절이 아니면 None."""
    cp = ord(ch)
    if not (_SYLLABLE_START <= cp <= _SYLLABLE_END):
        return None
    s = cp - _SYLLABLE_START
    cho = s // (_JUNG_COUNT * _JONG_COUNT)
    jung = (s % (_JUNG_COUNT * _JONG_COUNT)) // _JONG_COUNT
    jong = s % _JONG_COUNT
    return cho, jung, jong


def _compose_syllable(cho: int, jung: int, jong: int) -> str:
    """(초성, 중성, 종성) idx → 음절."""
    return chr(_SYLLABLE_START + (cho * _JUNG_COUNT + jung) * _JONG_COUNT + jong)


@dataclass(frozen=True)
class Variant:
    """생성된 변형 한 건.

    variant: 변형 표면 문자열.
    kind: 02 §3.4 variant_kind enum 중 하나 ('jamo'|'leet'|'chosung').
    """

    variant: str
    kind: str


# ---------------------------------------------------------------------------
# jamo — 전체 자모분리 표기
# ---------------------------------------------------------------------------
def _gen_jamo(surface: str) -> str:
    """전체 자모분리 표기. 음절은 호환 자모로 분해, 비한글은 보존.

    normalizer의 분해와 **동일한 호환 자모**를 사용하므로
    normalized_key(jamo) == normalized_key(surface)가 성립한다.
    (단, 비한글 부분의 NFKC·소문자화는 normalizer가 흡수한다.)
    """
    out: list[str] = []
    for ch in surface:
        d = _decompose_syllable(ch)
        if d is None:
            out.append(ch)
            continue
        cho, jung, jong = d
        out.append(_CHO[cho])
        out.append(_JUNG[jung])
        if jong:
            out.append(_JONG[jong])
    return "".join(out)


# ---------------------------------------------------------------------------
# chosung — 초성체
# ---------------------------------------------------------------------------
def _gen_chosung(surface: str) -> str:
    """초성체. 한글 음절은 초성 호환 자모만 남기고, 비한글은 보존.

    (예: '시발'→'ㅅㅂ', '운지'→'ㅇㅈ', '운G'→'ㅇG')
    """
    out: list[str] = []
    for ch in surface:
        d = _decompose_syllable(ch)
        if d is None:
            out.append(ch)
            continue
        out.append(_CHO[d[0]])
    return "".join(out)


# ---------------------------------------------------------------------------
# leet — 숫자/기호 치환 (근거 있는 한국어 leet)
# ---------------------------------------------------------------------------
# 음소(호환 자모) → leet 치환 후보. 도상 유사(글자 모양)·관용 치환만 수록한다.
# 과생성을 막기 위해 음절당 치환은 1~2곳으로 제한하고, 용어당 총량을 상한한다.
#
# 근거: 01 §3(도상 치환), 한국어 커뮤니티 관용(ㅣ↔1/l/i, ㅇ↔0/o).
# 'ㅏ↔r' 등 형태가 멀거나 일반어 충돌이 큰 치환은 의도적으로 제외(오탐 억제).
_LEET_JUNG: dict[str, tuple[str, ...]] = {
    "ㅣ": ("1", "l", "i"),  # 세로획 — 가장 흔한 도상 치환
}
_LEET_CHO: dict[str, tuple[str, ...]] = {
    "ㅇ": ("0", "o"),  # 원형 — 도상 치환
}

# 용어당 leet 변형 총량 상한 (조합 폭발 방지 — 명세 ≤ 20).
LEET_MAX_VARIANTS = 20


def _syllable_leet_forms(ch: str) -> list[str]:
    """음절 하나의 leet 치환형 목록(자기 자신 = 무치환은 제외).

    초성·중성 각각 최대 1곳 치환을 허용하되, 한 음절 내에서 동시에 두 곳을
    치환하지는 않는다(음절 내 1곳 — 단어 전체로는 최대 2음절까지 치환되어
    '음절 내 1~2곳' 명세를 만족).

    치환 표기 규칙(실제 사용 형태 반영):
      - 초성 치환: 초성을 도상 leet 문자로 바꾸고 나머지 자모는 펼친다
        (초성이 사라져 음절 재조합 불가 — 예: '운'의 ㅇ→0 → '0ㅜㄴ').
      - 중성 치환: 도상 leet 문자(1/l/i는 'ㅣ' 모양)는 모음을 **덧대는**
        형태로 흔히 쓰이므로, 음절은 그대로 두고 leet 문자를 음절 뒤에
        붙인다(예: '시'의 ㅣ→1 → '시1' → 단어로 '시1발'). 음절이 보존되어
        가독성이 높고 실제 회피에서 가장 흔하다.
    """
    d = _decompose_syllable(ch)
    if d is None:
        return []
    cho, jung, jong = d
    forms: list[str] = []

    # 초성 치환: 남은 (중성[+종성])은 음절 재조합 불가(초성 없음) → 펼침.
    cho_jamo = _CHO[cho]
    for leet in _LEET_CHO.get(cho_jamo, ()):  # 결정적 순서(튜플)
        rest = _JUNG[jung] + (_JONG[jong] if jong else "")
        forms.append(leet + rest)

    # 중성 치환: 음절은 보존하고 도상 leet 문자를 음절 뒤에 덧댄다.
    jung_jamo = _JUNG[jung]
    for leet in _LEET_JUNG.get(jung_jamo, ()):
        forms.append(ch + leet)

    return forms


def _gen_leet(surface: str) -> list[str]:
    """leet 변형 목록(결정적 순서, 상한 적용).

    전략(과생성 억제):
      1. 치환 가능 음절을 좌→우로 찾는다.
      2. 단일 음절 치환형을 먼저 모두 생성(가장 흔한 회피).
      3. 그다음 서로 다른 두 음절 동시 치환을 좌→우 쌍 순서로 생성.
      4. LEET_MAX_VARIANTS에서 절단.

    각 변형은 '치환된 음절만 leet형으로, 나머지 음절은 그대로' 둔 문자열이다.
    (예: '시발'의 '시' 중성 치환 → '시1발', '시l발' 등; '발'은 보존.)
    """
    syllables = list(surface)
    # 음절별 leet 후보 (인덱스 → [형식들]); 빈 리스트면 치환 불가.
    per_syll: list[list[str]] = [_syllable_leet_forms(ch) for ch in syllables]
    replaceable = [i for i, forms in enumerate(per_syll) if forms]

    results: list[str] = []
    seen: set[str] = set()

    def emit(parts: list[str]) -> None:
        s = "".join(parts)
        if s not in seen and s != surface:
            seen.add(s)
            results.append(s)

    # 2. 단일 음절 치환
    for i in replaceable:
        for form in per_syll[i]:
            parts = syllables.copy()
            parts[i] = form
            emit(parts)
            if len(results) >= LEET_MAX_VARIANTS:
                return results

    # 3. 두 음절 동시 치환 (i < j)
    for a in range(len(replaceable)):
        for b in range(a + 1, len(replaceable)):
            i, j = replaceable[a], replaceable[b]
            for fi in per_syll[i]:
                for fj in per_syll[j]:
                    parts = syllables.copy()
                    parts[i] = fi
                    parts[j] = fj
                    emit(parts)
                    if len(results) >= LEET_MAX_VARIANTS:
                        return results
    return results


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def generate_variants(surface: str) -> list[Variant]:
    """surface에서 변형 후보를 결정적으로 생성한다.

    순서 규약(결정성): jamo → chosung → leet.
    각 종류 내부도 결정적 순서를 유지한다. 빈/비한글/혼합 입력에 무예외.

    중복 variant 문자열(서로 다른 kind 간, 또는 surface와 동일)은 다음 규칙으로
    정리한다:
      - surface와 동일한 variant는 생성하지 않는다(자기 자신은 변형이 아님).
      - 한글이 전혀 없으면 jamo/chosung은 surface와 동일해지므로 비운다.
    """
    if not surface:
        return []

    variants: list[Variant] = []
    seen: set[str] = set()

    def add(text: str, kind: str) -> None:
        if not text or text == surface:
            return
        if text in seen:
            return
        seen.add(text)
        variants.append(Variant(variant=text, kind=kind))

    add(_gen_jamo(surface), "jamo")
    add(_gen_chosung(surface), "chosung")
    for leet in _gen_leet(surface):
        add(leet, "leet")

    return variants
