"""DartClient·profiler DART 노드 테스트 — 네트워크 무호출 (MockTransport·페이크)."""

import io
import json
import zipfile

import httpx
import pytest

import agent.dart_client as dart_client
from agent.dart_client import DartClient
from agent.profiler import ProfilerNodes, _format_dart_evidence


def _corp_zip() -> bytes:
    xml = (
        "<result>"
        "<list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>"
        "<stock_code>005930</stock_code></list>"
        "<list><corp_code>00999999</corp_code><corp_name>삼성전자서비스</corp_name>"
        "<stock_code></stock_code></list>"
        "<list><corp_code>00888888</corp_code><corp_name>(주)가나다</corp_name>"
        "<stock_code></stock_code></list>"
        "<list><corp_code>00777777</corp_code><corp_name>삼성</corp_name>"
        "<stock_code></stock_code></list>"
        "</result>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


def _client_with(handler, api_key="dart_key") -> DartClient:
    client = DartClient(api_key=api_key)
    transport = httpx.MockTransport(handler)
    original = httpx.Client

    class Patched(original):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    httpx.Client = Patched  # 테스트 안에서만 — 픽스처가 복원
    return client


@pytest.fixture(autouse=True)
def _restore_httpx_and_cache():
    original = httpx.Client
    dart_client._corp_cache.clear()
    yield
    httpx.Client = original
    dart_client._corp_cache.clear()


def test_requires_key():
    client = DartClient(api_key="")
    assert not client.available


def test_find_corp_prefers_exact_and_listed():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert "crtfc_key=dart_key" in str(request.url)
        return httpx.Response(200, content=_corp_zip())

    client = _client_with(handler)

    corp = client.find_corp("삼성전자")
    assert corp.corp_code == "00126380" and corp.listed

    # 정확 일치 + 법인 접두어 흡수만 자동 확정
    assert client.find_corp("삼성전자서비스").corp_code == "00999999"
    assert client.find_corp("가나다").corp_code == "00888888"
    assert client.find_corp("없는회사") is None
    # 종목코드 6자리는 그것으로 확정
    assert client.find_corp("005930").corp_code == "00126380"
    assert client.find_corp("삼성전자(005930)").corp_code == "00126380"
    # 부분 일치는 자동 선택 금지 — 엉뚱한 법인이 공식 원천을 오염시킴
    assert client.find_corp("삼성전") is None
    candidates = client.find_candidates("삼성전")
    assert [c.corp_code for c in candidates] == ["00126380", "00999999"]  # 상장 우선
    # 동명 함정: '삼성'이라는 비상장 법인이 정확 일치해도, 그 이름을 포함하는
    # 상장사(삼성전자)가 있으면 자동 확정하지 않는다 (DART 실데이터 재현)
    assert client.find_corp("삼성") is None
    # 비상장 정확 일치라도 상위 상장사가 없으면 그대로 확정 (삼성전자서비스)
    assert client.find_corp("삼성전자서비스").corp_code == "00999999"
    assert calls["count"] == 1  # corpCode ZIP은 1회만 (프로세스 캐시)


def test_finstate_prefers_consolidated_and_errors_on_bad_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if "fnlttSinglAcnt" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "status": "000",
                    "message": "정상",
                    "list": [
                        {"fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "1"},
                        {"fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "2"},
                    ],
                },
            )
        return httpx.Response(200, json={"status": "020", "message": "한도 초과"})

    client = _client_with(handler)
    rows = client.finstate("00126380", 2025)
    assert [r["fs_div"] for r in rows] == ["CFS"]  # 연결 우선

    with pytest.raises(ValueError, match="020"):
        client.company("00126380")


def test_format_dart_evidence_renders_sections():
    text = _format_dart_evidence(
        info={
            "corp_name": "삼성전자",
            "corp_cls": "Y",
            "stock_code": "005930",
            "ceo_nm": "대표님",
            "est_dt": "19690113",
            "acc_mt": "12",
            "adres": "수원시",
        },
        year=2025,
        rows=[
            {
                "account_nm": "매출액",
                "thstrm_nm": "제57기",
                "thstrm_amount": "300,870,903,000,000",
                "frmtrm_nm": "제56기",
                "frmtrm_amount": "258,935,494,000,000",
            }
        ],
        disclosures=[
            {"rcept_dt": "20260701", "report_nm": "주요사항보고서", "flr_nm": "삼성전자"}
        ],
    )
    assert "[기업개황]" in text
    assert "유가증권시장 상장, 종목코드 005930" in text
    assert "[주요 재무계정 — 2025년 사업보고서 기준" in text
    assert "매출액: 제57기 300,870,903,000,000 / 제56기 258,935,494,000,000" in text
    assert "[최근 90일 공시]" in text and "주요사항보고서" in text


# ── profiler dart 노드 ───────────────────────────────────────────────────


class FakeDart:
    def __init__(self, available=True, corp=None, candidates=None, fail=False):
        self._available = available
        self.corp = corp
        self.candidates = candidates or []
        self.fail = fail

    @property
    def available(self):
        return self._available

    def find_corp(self, name):
        if self.fail:
            raise ValueError("network down")
        return self.corp

    def find_candidates(self, name, limit=5):
        return self.candidates[:limit]

    def company(self, corp_code):
        return {"corp_name": "삼성전자", "corp_cls": "Y", "stock_code": "005930"}

    def finstate(self, corp_code, year, reprt_code="11011"):
        return [{"account_nm": "매출액", "thstrm_nm": "제57기", "thstrm_amount": "1,000"}]

    def recent_disclosures(self, corp_code, begin_date, count=10):
        return [{"rcept_dt": "20260701", "report_nm": "사업보고서", "flr_nm": "삼성전자"}]


def _nodes(dart) -> ProfilerNodes:
    from tests.test_profiler import FakeModel, FakeScraper, FakeSearcher

    return ProfilerNodes(
        model=FakeModel(), searcher=FakeSearcher(available=False),
        scraper=FakeScraper(), dart=dart,
    )


def test_dart_node_collects_evidence_and_source():
    from agent.dart_client import DartCorp

    nodes = _nodes(FakeDart(corp=DartCorp("00126380", "삼성전자", "005930")))
    update = nodes.dart_fetch({"company": "삼성전자"})
    assert "[기업개황]" in update["dart_evidence"]
    assert "매출액" in update["dart_evidence"]
    assert "DART 전자공시" in update["dart_source"]["title"]


def test_dart_node_skips_when_unavailable_or_unknown():
    nodes = _nodes(FakeDart(available=False))
    assert nodes.dart_fetch({"company": "삼성전자"}) == {}

    nodes = _nodes(FakeDart(corp=None))
    assert nodes.dart_fetch({"company": "이상한회사"}) == {}

    nodes = _nodes(FakeDart(fail=True))  # 예외도 브리핑을 중단시키지 않는다
    assert nodes.dart_fetch({"company": "삼성전자"}) == {}


def test_dart_node_ambiguous_name_skips_with_notice():
    from agent.dart_client import DartCorp
    from agent.profiler import CompanyProfile, _render_profile

    nodes = _nodes(
        FakeDart(
            corp=None,
            candidates=[
                DartCorp("00126380", "삼성전자", "005930"),
                DartCorp("00999999", "삼성전자서비스", ""),
            ],
        )
    )
    update = nodes.dart_fetch({"company": "삼성"})
    assert "dart_evidence" not in update  # 공시 미반영
    assert "삼성전자(005930)" in update["dart_notice"]
    assert "종목코드" in update["dart_notice"]

    # 안내문이 보고서에 렌더된다
    profile = CompanyProfile(company_overview="o", overall="s")
    out = _render_profile("삼성", profile, [], dart_notice=update["dart_notice"])
    assert "> '삼성' 명칭이 여러 DART 법인과 겹쳐" in out


def test_gather_proceeds_to_analyze_with_dart_only():
    nodes = _nodes(FakeDart(available=False))
    update = nodes.gather(
        {"company": "삼성전자", "provided_urls": [], "dart_evidence": "[기업개황] ..."}
    )
    assert update["error"] is None and update["sources"] == []
    assert nodes.route_gather({**update, "dart_evidence": "x"}) == "analyze"
