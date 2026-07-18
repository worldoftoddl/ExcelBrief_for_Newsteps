"""OpenDART 경량 클라이언트 — 기업이해(profiler)의 공식 공시 자료원.

OpenDartReader의 corp_code 매핑·주요 재무계정 접근 방식을 이 저장소
스타일(httpx·페이크 주입 테스트·pandas 무의존)로 얇게 포팅했다.
엔드포인트 4개만 쓴다:

  corpCode.xml     회사명 → corp_code 매핑 (ZIP, 프로세스 수명 캐시)
  company.json     기업개황 (업종·대표·설립·상장)
  fnlttSinglAcnt.json  주요 재무계정 (사업보고서, 연결 우선)
  list.json        최근 공시 목록

DART_API_KEY(opendart.fss.or.kr 무료 발급)가 없으면 available=False —
호출자는 DART 없이 강등 동작한다. 대상 호스트가 고정이라 SSRF 검증은
불필요하다.
"""

import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

import httpx

BASE_URL = "https://opendart.fss.or.kr/api"
ANNUAL_REPORT = "11011"  # 사업보고서

# corpCode ZIP(수 MB)은 비싸다 — 프로세스 수명 동안 키별로 1회만 받는다
_corp_cache: dict[str, list["DartCorp"]] = {}


@dataclass(frozen=True, slots=True)
class DartCorp:
    corp_code: str
    corp_name: str
    stock_code: str  # 비상장이면 빈 문자열

    @property
    def listed(self) -> bool:
        return bool(self.stock_code)


class DartClient:
    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("DART_API_KEY", "")
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # ── 저수준 호출 ──────────────────────────────────────────────────────
    def _get_bytes(self, path: str, **params) -> bytes:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{BASE_URL}/{path}", params={"crtfc_key": self.api_key, **params}
            )
            response.raise_for_status()
            return response.content

    def _get_json(self, path: str, **params) -> dict:
        payload = json.loads(self._get_bytes(path, **params).decode("utf-8"))
        if payload.get("status") not in ("000", "013"):  # 013 = 조회 결과 없음
            raise ValueError(
                f"DART 오류 {payload.get('status')}: {payload.get('message')}"
            )
        return payload

    # ── corp_code 매핑 ───────────────────────────────────────────────────
    def _corp_list(self) -> list[DartCorp]:
        if self.api_key in _corp_cache:
            return _corp_cache[self.api_key]
        raw = self._get_bytes("corpCode.xml")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml_bytes = archive.read(archive.namelist()[0])
        corps = []
        for node in ElementTree.fromstring(xml_bytes).iter("list"):
            corps.append(
                DartCorp(
                    corp_code=(node.findtext("corp_code") or "").strip(),
                    corp_name=(node.findtext("corp_name") or "").strip(),
                    stock_code=(node.findtext("stock_code") or "").strip(),
                )
            )
        _corp_cache[self.api_key] = corps
        return corps

    def find_corp(self, name: str) -> DartCorp | None:
        """종목코드 또는 정확 일치만 자동 확정한다 — 부분 일치 자동 선택 금지.

        '삼성'·'한화' 같은 모호한 이름이 엉뚱한 법인으로 이어지면 공식
        원천인 공시가 브리핑 전체를 오염시킨다. 부분 일치는 나열 전용인
        find_candidates 몫이고, 호출자는 후보를 사용자에게 안내해야 한다.
        """
        query = name.strip()
        if not query:
            return None
        corps = self._corp_list()
        # 종목코드 6자리가 있으면 그것으로 확정 (예: '삼성전자(005930)')
        code = re.search(r"(?<!\d)(\d{6})(?!\d)", query)
        if code:
            for corp in corps:
                if corp.stock_code == code.group(1):
                    return corp
        exact = [c for c in corps if c.corp_name == query]
        if not exact:
            # 법인 접두어 차이 흡수: '(주)삼성전자' ↔ '삼성전자'
            exact = [c for c in corps if c.corp_name.replace("(주)", "") == query]
        if exact:
            best = next((c for c in exact if c.listed), exact[0])
            if best.listed:
                return best
            # 동명 함정: DART에는 '삼성' 같은 이름의 무명 비상장 법인이
            # 실존한다 — 그 이름을 포함하는 상장사가 따로 있으면 사용자가
            # 그 상장사를 뜻했을 가능성이 높으므로 자동 확정하지 않는다
            listed_supersets = [
                c
                for c in corps
                if c.listed and query in c.corp_name and c.corp_name != query
            ]
            if listed_supersets:
                return None
            return best
        return None

    def find_candidates(self, name: str, limit: int = 5) -> list[DartCorp]:
        """부분 일치 후보 나열 — 상장 우선·이름 짧은 순. 자동 선택용이 아니다."""
        query = name.strip()
        if not query:
            return []
        partial = [c for c in self._corp_list() if query in c.corp_name]
        partial.sort(key=lambda c: (not c.listed, len(c.corp_name)))
        return partial[:limit]

    # ── 공시 데이터 ──────────────────────────────────────────────────────
    def company(self, corp_code: str) -> dict:
        """기업개황 — 대표자·업종·설립일·상장시장 등."""
        return self._get_json("company.json", corp_code=corp_code)

    def finstate(
        self, corp_code: str, year: int, reprt_code: str = ANNUAL_REPORT
    ) -> list[dict]:
        """주요 재무계정 (fnlttSinglAcnt) — 연결(CFS) 우선, 없으면 개별(OFS).

        결과 항목: account_nm(계정명)·thstrm_amount(당기)·frmtrm_amount(전기)
        등 OpenDART 원본 필드 그대로.
        """
        payload = self._get_json(
            "fnlttSinglAcnt.json",
            corp_code=corp_code,
            bsns_year=str(year),
            reprt_code=reprt_code,
        )
        rows = payload.get("list") or []
        consolidated = [r for r in rows if r.get("fs_div") == "CFS"]
        return consolidated or rows

    def recent_disclosures(
        self, corp_code: str, begin_date: str, count: int = 10
    ) -> list[dict]:
        """최근 공시 목록 — begin_date(YYYYMMDD)부터, 최신순."""
        payload = self._get_json(
            "list.json",
            corp_code=corp_code,
            bgn_de=begin_date,
            page_no="1",
            page_count=str(count),
        )
        return payload.get("list") or []
