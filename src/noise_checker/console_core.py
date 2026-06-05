"""검수 콘솔 순수 로직 (M1) — Streamlit 비의존.

docs/04-update-pipeline.md §3(candidate_queue)·§4(검수 워크플로우),
docs/02-database-design.md(스키마 정본), data/schema/candidate-payload.schema.json을
근거로 후보 큐 payload를 Lexicon DB 행 계획으로 변환하고, 단일 트랜잭션으로 적재한다.

핵심 불변식 (04 원칙 1):
  - 자동화는 후보 생성까지, active 전이는 **사람 검수 + DB 트리거**가 최종 방어.
    이 모듈은 term을 'in_review'(또는 needs_verification 시 'draft')까지만 적재한다.
    active 전환은 콘솔 UI의 별도 버튼 → DB 트리거가 evidence를 검사.
  - 모든 적재 행은 added_by/added_by 주체와 review_log에 검수자(reviewer)를 남긴다.

license_class 매핑 해석 (작업 지시 + docs/02 §3.1 주석·§5 게이트 의도):
  게이트(02 §5)는 '릴리스 아티팩트에 텍스트가 복제·재배포되는' 출처를 통제한다.
  뉴스(source_type='news')는 **사실(어떤 표현이 어디서 문제가 됐는지)만 추출**하고
  기사 본문을 복제하지 않으므로(04 §2·§7: 메타데이터+발췌만, 본문 전체 저장 금지),
  저작물 재배포 게이트의 차단 대상이 아니다. 따라서 뉴스 출처는 'unknown'으로 두어
  게이트에서 차단되게 하지 않고 license_class='permissive'로 적재하되,
  notes에 '뉴스: 사실 추출만, 본문 복제 금지'를 기록해 의도를 명시한다.
  (license 문자열의 '언론사 저작권' 표기에 끌려 restricted/unknown으로 분류하지 않는다.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .normalizer import normalized_key

__all__ = [
    "GatePreview",
    "PlannedWrites",
    "ApplyResult",
    "CHECKLIST_ITEMS",
    "license_class_from_string",
    "license_gate_preview",
    "payload_to_rows",
    "approve_candidate",
    "reject_candidate",
    "record_second_review",
]

# 라이선스 게이트 통과 집합 (02 §5) — 이외는 릴리스 차단.
_RELEASABLE = frozenset({"permissive", "share_alike"})

# 검수 체크리스트 5항목 (04 §4) — severity≥5 또는 법무 플래그면 전 항목 강제.
CHECKLIST_ITEMS: tuple[str, ...] = (
    "origin_source",      # ① origin 출처 ≥ 1 (청정 라이선스)
    "homonym_review",     # ② 동음이의어 검토 + safe_contexts
    "severity_basis",     # ③ severity 산정 근거
    "category",           # ④ 카테고리
    "legal_flag",         # ⑤ 법무 플래그 (실명/노출 여부)
)


# ---------------------------------------------------------------------------
# 게이트 0 프리뷰 (순수)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GatePreview:
    """라이선스 게이트 0 판정 결과 + 파생 메타(02 §3.2·§5)."""

    passes: bool
    blocking: list[str]            # 차단을 유발한 license_class 값 (정렬·유니크)
    effective_license: str         # SA 포함 시 'CC BY-SA 4.0', 아니면 '자체'
    provenance_class: str          # permissive_core / share_alike_core / restricted_eval_only
    reason: str


def license_gate_preview(license_classes: list[str]) -> GatePreview:
    """연결 evidence source들의 license_class 목록으로 게이트 0을 판정한다.

    - 전부 {permissive, share_alike} → 통과.
    - noncommercial/no_derivatives/restricted/unknown 이 하나라도 → 차단.
    - effective_license: share_alike 포함 시 'CC BY-SA 4.0', 아니면 '자체'.
    - provenance_class (02 §3.2):
        · 차단(restricted/NC/ND/unknown 포함) → restricted_eval_only
        · share_alike 포함(차단 없음)        → share_alike_core
        · 전부 permissive/internal           → permissive_core
    """
    classes = list(license_classes)
    blocking = sorted({c for c in classes if c not in _RELEASABLE})
    has_share_alike = "share_alike" in classes

    if blocking:
        return GatePreview(
            passes=False,
            blocking=blocking,
            effective_license="CC BY-SA 4.0" if has_share_alike else "자체",
            provenance_class="restricted_eval_only",
            reason=f"릴리스 차단 license_class 존재: {', '.join(blocking)}",
        )
    if not classes:
        # evidence가 아직 없으면 게이트를 통과로 보지 않는다 (보수적).
        return GatePreview(
            passes=False,
            blocking=[],
            effective_license="자체",
            provenance_class="restricted_eval_only",
            reason="연결 evidence source 없음 — 게이트 판정 불가",
        )
    if has_share_alike:
        return GatePreview(
            passes=True,
            blocking=[],
            effective_license="CC BY-SA 4.0",
            provenance_class="share_alike_core",
            reason="share_alike 포함 — SA 전파(attribution) 의무",
        )
    return GatePreview(
        passes=True,
        blocking=[],
        effective_license="자체",
        provenance_class="permissive_core",
        reason="전부 permissive/internal",
    )


# ---------------------------------------------------------------------------
# license 문자열 → license_class 휴리스틱 (순수)
# ---------------------------------------------------------------------------
def license_class_from_string(license_text: str | None, source_type: str) -> tuple[str, str | None]:
    """원자료의 사람 가독 라이선스 문자열을 license_class enum으로 매핑한다.

    Returns (license_class, note) — note는 source.notes에 덧붙일 보조 설명(없으면 None).

    매핑 규칙 (02 §3.1, 작업 지시 휴리스틱):
      · 'CC BY-SA' / 'CC-BY-SA'        → share_alike
      · 'CC BY-NC' / '-NC'             → noncommercial
      · '-ND' / 'NoDerivatives'        → no_derivatives
      · 'MIT' / 'Apache' / 'CC BY '(NC/SA 아님) / 'CC0' / 'public domain' → permissive
      · source_type='news'             → permissive (사실 추출만; note 기록 — 위 docstring 해석)
      · source_type='internal'         → permissive (자체 작성)
      · 그 외/불명                      → unknown (NC와 동일하게 차단이 기본값, 02 §5)
    """
    text = (license_text or "").strip()
    upper = text.upper().replace("-", " ")  # 'CC-BY-SA' → 'CC BY SA'

    # 가장 제한적인 신호부터 검사 (NC/ND가 BY-SA·BY보다 우선)
    if "BY SA" in upper or "SHAREALIKE" in upper or "SHARE ALIKE" in upper:
        return "share_alike", None
    if "NC" in upper.split() or "NONCOMMERCIAL" in upper or "NON COMMERCIAL" in upper:
        return "noncommercial", None
    if "ND" in upper.split() or "NODERIVATIVES" in upper or "NO DERIVATIVES" in upper:
        return "no_derivatives", None
    if (
        "MIT" in upper
        or "APACHE" in upper
        or "CC0" in upper
        or "PUBLIC DOMAIN" in upper
        or "BY " in upper.replace("CC BY", "CC BY ")  # 'CC BY 4.0' 류 permissive BY
        or upper.startswith("CC BY")
    ):
        return "permissive", None

    # 뉴스: 본문 복제가 아니라 사실 추출이므로 게이트 차단 대상이 아님.
    if source_type == "news":
        note = "뉴스 출처: 사실 추출만, 본문 복제 금지 (release_policy 게이트 비대상)"
        return "permissive", note
    if source_type == "internal":
        return "permissive", None

    # 불명 — NC와 동일하게 차단 기본값.
    return "unknown", None


# ---------------------------------------------------------------------------
# 행 계획 (순수)
# ---------------------------------------------------------------------------
@dataclass
class SourceRow:
    url: str | None
    title: str
    source_type: str
    license: str | None
    license_class: str
    publisher: str | None
    reliability: int
    archive_url: str | None
    notes: str | None
    evidence_type: str          # 이 source가 term에 어떤 증거로 연결되는지
    excerpt: str | None


@dataclass
class PlannedWrites:
    """payload → 적재 행 계획. approve_candidate가 단일 트랜잭션으로 실행한다."""

    kind: str
    reviewer: str
    # term ----------------------------------------------------------------
    term: dict[str, Any] | None = None
    sources: list[SourceRow] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    composite_rules: list[dict[str, Any]] = field(default_factory=list)
    incidents: list[dict[str, Any]] = field(default_factory=list)
    # new_marker ----------------------------------------------------------
    marker: dict[str, Any] | None = None
    # new_variant (기존 term에 변형 추가) ---------------------------------
    variant_for_parent: dict[str, Any] | None = None
    # deprecation (review_log 기록만) -------------------------------------
    deprecation: dict[str, Any] | None = None
    # 게이트 프리뷰 (term/marker 적재 시 provenance_class 산출에 사용) -----
    gate: GatePreview | None = None


def _term_status(needs_verification: bool) -> str:
    """needs_verification=true → 'draft' 고정, 아니면 'in_review' (04 §4·스키마)."""
    return "draft" if needs_verification else "in_review"


def payload_to_rows(payload: dict[str, Any], kind: str, reviewer: str) -> PlannedWrites:
    """candidate_queue 한 행(payload)을 kind에 맞는 적재 계획으로 변환한다 (순수).

    new_term  → source(URL dedupe)/term/term_evidence/term_category/term_variant/
                composite_rule/incident 계획.
    new_marker→ image_marker(draft, advisory_only) + marker source/evidence.
    new_variant→ 기존 term에 term_variant 추가.
    incident  → incident 행 (legal_reviewed=false, disclosable=false).
    deprecation→ review_log 기록만.
    """
    if kind == "new_term":
        return _plan_new_term(payload, reviewer)
    if kind == "new_marker":
        return _plan_new_marker(payload, reviewer)
    if kind == "new_variant":
        return _plan_new_variant(payload, reviewer)
    if kind == "incident":
        return _plan_incident(payload, reviewer)
    if kind == "deprecation":
        return PlannedWrites(kind=kind, reviewer=reviewer, deprecation=dict(payload))
    raise ValueError(f"지원하지 않는 kind: {kind}")


def _plan_new_term(payload: dict[str, Any], reviewer: str) -> PlannedWrites:
    surface = payload["surface"]
    term_kind = payload.get("term_kind", "word")
    needs_verification = bool(payload.get("needs_verification", False))

    # evidence → source 행 (license_class 매핑). URL dedupe는 적재 단계에서 처리.
    sources: list[SourceRow] = []
    license_classes: list[str] = []
    for ev in payload.get("evidence", []):
        lic_class, lic_note = license_class_from_string(
            ev.get("license"), ev["source_type"]
        )
        license_classes.append(lic_class)
        sources.append(
            SourceRow(
                url=ev.get("url"),
                title=ev["title"],
                source_type=ev["source_type"],
                license=ev.get("license"),
                license_class=lic_class,
                publisher=ev.get("publisher"),
                reliability=int(ev.get("reliability", 3)),
                archive_url=ev.get("archive_url"),
                notes=lic_note,
                evidence_type=ev["evidence_type"],
                excerpt=_clip_excerpt(ev.get("excerpt")),
            )
        )

    gate = license_gate_preview(license_classes)

    term = {
        "surface": surface,
        "normalized_key": normalized_key(surface),
        "term_kind": term_kind,
        "origin_community": payload.get("origin_community"),
        "origin_story": payload["origin_story"],
        "origin_period": payload.get("origin_period"),
        "meaning": payload["meaning"],
        "severity": int(payload["severity"]),
        "ambiguity": payload.get("ambiguity", "unambiguous"),
        "safe_contexts": payload.get("safe_contexts") or None,
        # status: needs_verification → draft, 아니면 in_review (active 직접 적재 금지)
        "status": _term_status(needs_verification),
        # provenance_class: 게이트 프리뷰가 evidence에서 산출한 값을 적재.
        "provenance_class": gate.provenance_class,
    }

    variants = [
        {
            "variant": v["variant"],
            "variant_kind": v["variant_kind"],
            "normalized_key": normalized_key(v["variant"]),
            "auto_generated": False,
            "verified": False,            # 검수자 확인 전 — 02 §3.4
            "source_url": v.get("source_url"),
        }
        for v in payload.get("variants_observed", [])
    ]

    composite_rules = [
        {
            "trigger_kind": r["trigger_kind"],
            "trigger_terms_surface": r.get("trigger_terms_surface"),
            "trigger_pattern": r.get("trigger_pattern"),
            "proximity_window": r.get("proximity_window"),
            "base_severity": int(r["base_severity"]),
            "severity_delta": int(r["severity_delta"]),
            "status": "draft",            # 조합 규칙도 검수 거침 — draft 적재
        }
        for r in payload.get("combination_rules", [])
    ]

    incidents = [
        {
            "title": inc["title"],
            "occurred_at": _coerce_partial_date(inc.get("occurred_at")),
            "medium": inc.get("medium"),
            "sample_text": inc.get("sample_text"),
            "source_url": inc.get("source_url"),
            "legal_reviewed": False,      # 02 §3.7 — 자동 노출 불가
            "disclosable": False,
        }
        for inc in payload.get("related_incidents", [])
    ]

    return PlannedWrites(
        kind="new_term",
        reviewer=reviewer,
        term=term,
        sources=sources,
        categories=list(payload.get("categories", [])),
        variants=variants,
        composite_rules=composite_rules,
        incidents=incidents,
        gate=gate,
    )


def _plan_new_marker(payload: dict[str, Any], reviewer: str) -> PlannedWrites:
    lic_class, lic_note = license_class_from_string(payload.get("license_note"), "internal")
    gate = license_gate_preview([lic_class])
    source = SourceRow(
        url=payload.get("source_url"),
        title=payload["name"],
        source_type="internal",
        license=payload.get("license_note"),
        license_class=lic_class,
        publisher=None,
        reliability=3,
        archive_url=None,
        notes=lic_note,
        evidence_type="origin",
        excerpt=None,
    )
    marker = {
        "name": payload["name"],
        "marker_kind": payload["marker_kind"],
        "origin_story": payload["origin_note"],
        "severity": int(payload.get("severity", 3)),
        # M4 전: 존재·출처 기록만. draft + advisory_only (02 §3.6 표식 기본값).
        "status": "draft",
        "release_policy": "advisory_only",
        "provenance_class": gate.provenance_class,
        "detection_method": payload.get("detection_method") or ["phash"],
    }
    return PlannedWrites(
        kind="new_marker",
        reviewer=reviewer,
        marker=marker,
        sources=[source],
        gate=gate,
    )


def _plan_new_variant(payload: dict[str, Any], reviewer: str) -> PlannedWrites:
    variant = {
        "parent_term_id": payload.get("parent_term_id"),
        "parent_surface": payload.get("parent_surface"),
        "variant": payload["variant"],
        "variant_kind": payload["variant_kind"],
        "normalized_key": normalized_key(payload["variant"]),
        "auto_generated": False,
        "verified": False,
        "source_url": payload.get("source_url"),
    }
    return PlannedWrites(kind="new_variant", reviewer=reviewer, variant_for_parent=variant)


def _plan_incident(payload: dict[str, Any], reviewer: str) -> PlannedWrites:
    incident = {
        "title": payload["title"],
        "occurred_at": payload.get("occurred_at"),
        "medium": payload.get("medium"),
        "sample_text": payload.get("sample_text"),
        "source_url": payload.get("source_url"),
        "related_surface": payload.get("related_surface"),
        "related_marker": payload.get("related_marker"),
        "legal_reviewed": False,
        "disclosable": False,
    }
    return PlannedWrites(kind="incident", reviewer=reviewer, incidents=[incident])


def _clip_excerpt(excerpt: str | None) -> str | None:
    """term_evidence.excerpt CHECK(<=300)을 앱 레이어에서 선제 절단 (저작권 보수)."""
    if excerpt is None:
        return None
    return excerpt[:300]


# ---------------------------------------------------------------------------
# 트랜잭션 적용 (DB) — sqlalchemy Connection.execute(text(...)) 사용
# ---------------------------------------------------------------------------
@dataclass
class ApplyResult:
    candidate_id: int
    kind: str
    term_id: int | None = None
    marker_id: int | None = None
    variant_ids: list[int] = field(default_factory=list)
    composite_rule_ids: list[int] = field(default_factory=list)
    incident_ids: list[int] = field(default_factory=list)
    source_ids: list[int] = field(default_factory=list)


def _requires_full_checklist(planned: PlannedWrites, legal_review_flag: bool) -> bool:
    """severity≥5 또는 법무 플래그면 풀 체크리스트 강제 (04 §4 검수 강도 차등)."""
    if legal_review_flag:
        return True
    severity = 0
    if planned.term is not None:
        severity = int(planned.term.get("severity", 0))
    elif planned.marker is not None:
        severity = int(planned.marker.get("severity", 0))
    return severity >= 5


def _enforce_checklist(planned: PlannedWrites, checklist: dict, legal_review_flag: bool) -> None:
    if not _requires_full_checklist(planned, legal_review_flag):
        return
    missing = [item for item in CHECKLIST_ITEMS if not checklist.get(item)]
    if missing:
        raise ValueError(
            "severity≥5 또는 법무 플래그 항목은 풀 체크리스트 필수 — 미충족: "
            + ", ".join(missing)
        )


def _checklist_summary(checklist: dict) -> str:
    done = [item for item in CHECKLIST_ITEMS if checklist.get(item)]
    return "체크리스트 통과: " + (", ".join(done) if done else "(없음)")


def approve_candidate(
    conn, candidate_id: int, reviewer: str, checklist: dict
) -> ApplyResult:
    """후보를 승인하고 계획 행을 단일 트랜잭션으로 적재한다.

    1) candidate_queue에서 payload/kind 조회 (status='pending' 가정)
    2) payload_to_rows로 계획 산출 + 체크리스트 강제(severity≥5/법무 플래그)
    3) source(URL dedupe)/term/evidence/category/variant/composite_rule/incident 적재
    4) candidate_queue.status='approved' + review_log(action='approved') 기록

    실패 시 호출자 트랜잭션 컨텍스트가 롤백된다(이 함수는 commit하지 않는다 —
    sqlalchemy `with engine.begin()`/`conn.begin()` 안에서 호출).
    """
    from sqlalchemy import text

    row = conn.execute(
        text("SELECT payload, kind, status FROM candidate_queue WHERE id = :id"),
        {"id": candidate_id},
    ).fetchone()
    if row is None:
        raise ValueError(f"후보 {candidate_id} 없음")
    payload, kind, status = row[0], row[1], row[2]
    if status != "pending":
        raise ValueError(f"후보 {candidate_id} 상태가 pending이 아님: {status}")

    legal_review_flag = (
        bool(payload.get("legal_review_flag", False)) if isinstance(payload, dict) else False
    )
    planned = payload_to_rows(payload, kind, reviewer)
    _enforce_checklist(planned, checklist, legal_review_flag)

    result = ApplyResult(candidate_id=candidate_id, kind=kind)

    if kind == "new_term":
        _apply_new_term(conn, planned, reviewer, checklist, result)
    elif kind == "new_marker":
        _apply_new_marker(conn, planned, reviewer, checklist, result)
    elif kind == "new_variant":
        _apply_new_variant(conn, planned, reviewer, checklist, result)
    elif kind == "incident":
        _apply_incident(conn, planned, reviewer, result)
    elif kind == "deprecation":
        _apply_deprecation(conn, planned, reviewer, result)
    else:  # pragma: no cover — payload_to_rows가 이미 거름
        raise ValueError(f"지원하지 않는 kind: {kind}")

    conn.execute(
        text("UPDATE candidate_queue SET status='approved' WHERE id=:id"),
        {"id": candidate_id},
    )
    return result


def _upsert_source(conn, src: SourceRow) -> int:
    """URL이 있으면 UNIQUE(url)로 dedupe, 없으면 항상 새 행."""
    from sqlalchemy import text

    if src.url:
        existing = conn.execute(
            text("SELECT id FROM source WHERE url = :url"), {"url": src.url}
        ).fetchone()
        if existing is not None:
            return existing[0]
    sid = conn.execute(
        text(
            "INSERT INTO source (url, title, source_type, publisher, license, "
            "license_class, reliability, archive_url, notes) "
            "VALUES (:url, :title, :source_type, :publisher, :license, "
            ":license_class, :reliability, :archive_url, :notes) RETURNING id"
        ),
        {
            "url": src.url,
            "title": src.title,
            "source_type": src.source_type,
            "publisher": src.publisher,
            "license": src.license,
            "license_class": src.license_class,
            "reliability": src.reliability,
            "archive_url": src.archive_url,
            "notes": src.notes,
        },
    ).fetchone()[0]
    return sid


def _apply_new_term(
    conn, planned: PlannedWrites, reviewer: str, checklist: dict, result: ApplyResult
) -> None:
    from sqlalchemy import text

    term = planned.term
    assert term is not None
    term_id = conn.execute(
        text(
            "INSERT INTO term (surface, normalized_key, term_kind, origin_community, "
            "origin_story, origin_period, meaning, severity, ambiguity, safe_contexts, "
            "status, provenance_class) VALUES (:surface, :normalized_key, :term_kind, "
            ":origin_community, :origin_story, :origin_period, :meaning, :severity, "
            ":ambiguity, :safe_contexts, :status, :provenance_class) RETURNING id"
        ),
        term,
    ).fetchone()[0]
    result.term_id = term_id

    # source dedupe + term_evidence
    for src in planned.sources:
        sid = _upsert_source(conn, src)
        result.source_ids.append(sid)
        conn.execute(
            text(
                "INSERT INTO term_evidence (term_id, source_id, evidence_type, excerpt, added_by) "
                "VALUES (:t, :s, :et, :ex, :by) "
                "ON CONFLICT (term_id, source_id, evidence_type) DO NOTHING"
            ),
            {"t": term_id, "s": sid, "et": src.evidence_type, "ex": src.excerpt, "by": reviewer},
        )

    # term_category (코드 → category.id)
    for code in planned.categories:
        conn.execute(
            text(
                "INSERT INTO term_category (term_id, category_id) "
                "SELECT :t, id FROM category WHERE code = :code "
                "ON CONFLICT DO NOTHING"
            ),
            {"t": term_id, "code": code},
        )

    # term_variant (verified=false)
    for v in planned.variants:
        vid = conn.execute(
            text(
                "INSERT INTO term_variant (term_id, variant, variant_kind, normalized_key, "
                "auto_generated, verified) "
                "VALUES (:t, :variant, :variant_kind, :nkey, false, false) "
                "ON CONFLICT (term_id, variant) DO NOTHING RETURNING id"
            ),
            {"t": term_id, "variant": v["variant"], "variant_kind": v["variant_kind"],
             "nkey": v["normalized_key"]},
        ).fetchone()
        if vid is not None:
            result.variant_ids.append(vid[0])

    # composite_rule (draft) — trigger_terms_surface는 M1에선 미해석(검수자가 보완)
    for r in planned.composite_rules:
        rid = conn.execute(
            text(
                "INSERT INTO composite_rule (primary_term_id, trigger_kind, trigger_pattern, "
                "proximity_window, base_severity, severity_delta, status) "
                "VALUES (:t, :tk, :tp, :pw, :bs, :sd, 'draft') RETURNING id"
            ),
            {"t": term_id, "tk": r["trigger_kind"], "tp": r.get("trigger_pattern"),
             "pw": r.get("proximity_window"), "bs": r["base_severity"], "sd": r["severity_delta"]},
        ).fetchone()[0]
        result.composite_rule_ids.append(rid)

    # related incidents (term_id 연결, legal_reviewed/disclosable=false)
    for inc in planned.incidents:
        iid = _insert_incident(conn, inc, term_id=term_id, marker_id=None)
        result.incident_ids.append(iid)

    _log(conn, "term", term_id, "approved", reviewer, _checklist_summary(checklist),
         new_value={"status": term["status"], "provenance_class": term["provenance_class"]})


def _apply_new_marker(
    conn, planned: PlannedWrites, reviewer: str, checklist: dict, result: ApplyResult
) -> None:
    from sqlalchemy import text

    marker = planned.marker
    assert marker is not None
    marker_id = conn.execute(
        text(
            "INSERT INTO image_marker (name, marker_kind, origin_story, severity, "
            "detection_method, status, release_policy, provenance_class) "
            "VALUES (:name, :marker_kind, :origin_story, :severity, :detection_method, "
            ":status, :release_policy, :provenance_class) RETURNING id"
        ),
        marker,
    ).fetchone()[0]
    result.marker_id = marker_id

    for src in planned.sources:
        sid = _upsert_source(conn, src)
        result.source_ids.append(sid)
        conn.execute(
            text(
                "INSERT INTO marker_evidence "
                "(marker_id, source_id, evidence_type, excerpt, added_by) "
                "VALUES (:m, :s, :et, :ex, :by) "
                "ON CONFLICT (marker_id, source_id, evidence_type) DO NOTHING"
            ),
            {"m": marker_id, "s": sid, "et": src.evidence_type, "ex": src.excerpt, "by": reviewer},
        )

    _log(conn, "image_marker", marker_id, "approved", reviewer, _checklist_summary(checklist),
         new_value={"status": marker["status"], "release_policy": marker["release_policy"]})


def _apply_new_variant(
    conn, planned: PlannedWrites, reviewer: str, checklist: dict, result: ApplyResult
) -> None:
    from sqlalchemy import text

    v = planned.variant_for_parent
    assert v is not None
    term_id = _resolve_parent_term(conn, v.get("parent_term_id"), v.get("parent_surface"))
    if term_id is None:
        raise ValueError(
            "부모 용어를 찾을 수 없음 "
            f"(id={v.get('parent_term_id')}, surface={v.get('parent_surface')})"
        )
    vid = conn.execute(
        text(
            "INSERT INTO term_variant (term_id, variant, variant_kind, normalized_key, "
            "auto_generated, verified) VALUES (:t, :variant, :variant_kind, :nkey, false, false) "
            "ON CONFLICT (term_id, variant) DO NOTHING RETURNING id"
        ),
        {"t": term_id, "variant": v["variant"], "variant_kind": v["variant_kind"],
         "nkey": v["normalized_key"]},
    ).fetchone()
    if vid is not None:
        result.variant_ids.append(vid[0])
        result.term_id = term_id
        _log(conn, "variant", vid[0], "approved", reviewer, _checklist_summary(checklist),
             new_value={"variant": v["variant"], "parent_term_id": term_id})


def _apply_incident(conn, planned: PlannedWrites, reviewer: str, result: ApplyResult) -> None:
    for inc in planned.incidents:
        term_id = _resolve_parent_term(conn, None, inc.get("related_surface"))
        # term으로 해석 안 되면 marker일 수 있다 (예: 집게손가락). 둘 다 없으면
        # incident_check 제약(term_id OR marker_id) 위반이므로 명확한 오류로 안내.
        marker_id = None
        if term_id is None:
            marker_id = _resolve_parent_marker(conn, inc.get("related_surface"))
        if term_id is None and marker_id is None:
            raise ValueError(
                f"incident '{inc.get('title', '?')[:40]}'의 related_surface"
                f"({inc.get('related_surface')!r})를 term/marker로 해석할 수 없음 — "
                "관련 용어/표식 후보를 먼저 승인하세요"
            )
        iid = _insert_incident(conn, inc, term_id=term_id, marker_id=marker_id)
        result.incident_ids.append(iid)
        # incident는 review_log entity_type에 없으므로 관련 term이 있으면 그 term에 기록.
        if term_id is not None:
            _log(conn, "term", term_id, "incident_added", reviewer,
                 f"incident #{iid} 연결 (legal_reviewed=false, disclosable=false)")


def _apply_deprecation(conn, planned: PlannedWrites, reviewer: str, result: ApplyResult) -> None:
    dep = planned.deprecation or {}
    term_id = _resolve_parent_term(conn, dep.get("target_term_id"), dep.get("target_surface"))
    if term_id is not None:
        result.term_id = term_id
        _log(conn, "term", term_id, "deprecation_proposed", reviewer,
             dep.get("inactivity_basis", "무활동 근거 미기재"))


def _coerce_partial_date(value: Any) -> Any:
    """payload의 부분 날짜('YYYY-MM'/'YYYY')를 date 컬럼용으로 1일 보정.

    후보 스키마는 발생 시점을 월 단위까지만 아는 경우를 허용하지만
    incident.occurred_at은 date 타입이므로 경계에서 보정한다.
    """
    if isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}", value):
            return value + "-01"
        if re.fullmatch(r"\d{4}", value):
            return value + "-01-01"
    return value


def _insert_incident(conn, inc: dict, term_id: int | None, marker_id: int | None) -> int:
    from sqlalchemy import text

    # incident는 source_id NOT NULL — source_url로 source를 dedupe 등록한다.
    src = SourceRow(
        url=inc.get("source_url"),
        title=inc["title"],
        source_type="news",
        license=None,
        license_class="permissive",  # 뉴스: 사실 추출만 (위 해석)
        publisher=None,
        reliability=4,
        archive_url=None,
        notes="뉴스 출처: 사실 추출만, 본문 복제 금지",
        evidence_type="incident",
        excerpt=None,
    )
    source_id = _upsert_source(conn, src)
    iid = conn.execute(
        text(
            "INSERT INTO incident (title, occurred_at, medium, term_id, marker_id, "
            "source_id, sample_text, description, legal_reviewed, disclosable) "
            "VALUES (:title, :occurred_at, :medium, :term_id, :marker_id, :source_id, "
            ":sample_text, :description, false, false) RETURNING id"
        ),
        {
            "title": inc["title"],
            "occurred_at": _coerce_partial_date(inc.get("occurred_at")),
            "medium": inc.get("medium"),
            "term_id": term_id,
            "marker_id": marker_id,
            "source_id": source_id,
            "sample_text": inc.get("sample_text"),
            "description": inc.get("title"),  # description NOT NULL — 제목으로 초안, 검수자 보완
        },
    ).fetchone()[0]
    return iid


def _resolve_parent_marker(conn, surface: str | None) -> int | None:
    from sqlalchemy import text

    if not surface:
        return None
    # marker 이름은 '이름 (부연 설명)' 규약 — 부연 앞부분 일치도 허용.
    row = conn.execute(
        text(
            "SELECT id FROM image_marker "
            "WHERE name=:n OR split_part(name, ' (', 1)=:n ORDER BY id LIMIT 1"
        ),
        {"n": surface},
    ).fetchone()
    return row[0] if row is not None else None


def _resolve_parent_term(conn, term_id: Any, surface: str | None) -> int | None:
    from sqlalchemy import text

    if term_id is not None:
        try:
            tid = int(term_id)
        except (TypeError, ValueError):
            tid = None
        if tid is not None:
            row = conn.execute(text("SELECT id FROM term WHERE id=:id"), {"id": tid}).fetchone()
            if row is not None:
                return row[0]
    if surface:
        row = conn.execute(
            text("SELECT id FROM term WHERE normalized_key=:nk ORDER BY id LIMIT 1"),
            {"nk": normalized_key(surface)},
        ).fetchone()
        if row is not None:
            return row[0]
    return None


def reject_candidate(conn, candidate_id: int, reviewer: str, reason: str) -> None:
    """후보를 반려한다 (status='rejected' + review_log)."""
    from sqlalchemy import text

    row = conn.execute(
        text("SELECT kind, status FROM candidate_queue WHERE id=:id"),
        {"id": candidate_id},
    ).fetchone()
    if row is None:
        raise ValueError(f"후보 {candidate_id} 없음")
    conn.execute(
        text("UPDATE candidate_queue SET status='rejected' WHERE id=:id"),
        {"id": candidate_id},
    )
    # 아직 적재된 엔티티가 없으므로 candidate id 자체를 entity_id로 기록 (entity_type='term' 관례).
    _log(conn, "term", candidate_id, "rejected", reviewer, reason,
         new_value={"candidate_id": candidate_id, "reason": reason})


def record_second_review(
    conn, entity_type: str, entity_id: int, reviewer: str, agree: bool, note: str
) -> None:
    """IAA 이중검수 기록 (review_log action='second_review')."""
    _log(
        conn, entity_type, entity_id, "second_review", reviewer,
        note, new_value={"agree": agree},
    )


def _log(
    conn, entity_type: str, entity_id: int, action: str, reviewer: str,
    rationale: str | None, *, old_value: dict | None = None, new_value: dict | None = None,
) -> None:
    import json

    from sqlalchemy import text

    conn.execute(
        text(
            "INSERT INTO review_log (entity_type, entity_id, action, old_value, new_value, "
            "reviewer, rationale) VALUES (:et, :eid, :action, "
            "CAST(:old AS JSONB), CAST(:new AS JSONB), :reviewer, :rationale)"
        ),
        {
            "et": entity_type,
            "eid": entity_id,
            "action": action,
            "old": json.dumps(old_value) if old_value is not None else None,
            "new": json.dumps(new_value) if new_value is not None else None,
            "reviewer": reviewer,
            "rationale": rationale,
        },
    )
