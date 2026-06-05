"""테스트 공용 픽스처 — release_test 아티팩트를 임시 디렉토리로 머티리얼라이즈.

fixtures/release_test/manifest.json의 normalizer_code_version은 환경 의존(소스
해시 또는 M2-A가 추가할 NORMALIZER_VERSION)이므로 플레이스홀더로 두고, 테스트
시점에 compiled_normalizer_version()으로 주입해 유효한 릴리스 디렉토리를 만든다.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from noise_checker.engine import Engine, compiled_normalizer_version

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "release_test"


def materialize_release(dest: Path, *, normalizer_version: str | None = None) -> Path:
    """fixtures/release_test를 dest로 복사하고 manifest 버전을 주입한다.

    normalizer_version을 명시하면 그 값으로 덮어써(불일치 로드 거부 테스트용),
    생략하면 compiled_normalizer_version()(정상 로드)을 쓴다.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("terms.json", "kiwi_user_dict.tsv"):
        shutil.copy(FIXTURE_DIR / name, dest / name)
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["normalizer_code_version"] = (
        normalizer_version if normalizer_version is not None else compiled_normalizer_version()
    )
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return dest


@pytest.fixture
def release_dir(tmp_path: Path) -> Path:
    """유효한 릴리스 아티팩트 디렉토리 (정상 normalizer 버전)."""
    return materialize_release(tmp_path / "release")


@pytest.fixture(scope="session")
def engine(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """release_test 아티팩트로 로드한 엔진 (세션 1회 — Kiwi 콜드스타트 비용 절감).

    엔진은 상태를 변경하지 않는 읽기 전용이므로 세션 공유가 안전하다.
    """
    dest = materialize_release(tmp_path_factory.mktemp("release"))
    return Engine.load(dest)
