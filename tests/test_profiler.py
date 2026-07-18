"""기업이해(profiler) 그래프 테스트 — 네트워크·LLM 무호출 (전부 페이크 주입)."""

from types import SimpleNamespace

from agent.profiler import (
    NO_SOURCE_MESSAGE,
    CompanyProfile,
    IssueNote,
    ProfilePlan,
    ProfilerNodes,
    RiskCandidate,
    TriageDecision,
    _render_profile,
)
from agent.scraping import SearchHit
from langchain_core.messages import HumanMessage


class FakeModel:
    """스키마별 준비된 값을 돌려주는 구조화 출력 페이크."""

    def __init__(self, structured=None):
        self.structured = structured or {}

    def with_structured_output(self, schema):
        if schema not in self.structured:
            def _raise(_messages):
                raise ValueError(f"no fake for {schema}")

            return SimpleNamespace(invoke=_raise)
        return SimpleNamespace(invoke=lambda _messages: self.structured[schema])


class FakeSearcher:
    def __init__(self, hits=None, available=True):
        self.hits = hits or []
        self._available = available
        self.queries = []  # [(query, topic)]

    @property
    def available(self):
        return self._available

    def search(self, query, max_results=5, topic="general"):
        self.queries.append((query, topic))
        return self.hits[:max_results]


class FakeScraper:
    """URL별 추출 결과(또는 예외)를 돌려주는 웹 추출 서브그래프 페이크."""

    def __init__(self, results=None):
        self.results = results or {}

    def invoke(self, request):
        value = self.results.get(request["url"], "추출된 내용")
        if isinstance(value, Exception):
            raise value
        return {"result": value, "error": None, "final_url": request["url"]}


def _sample_profile() -> CompanyProfile:
    return CompanyProfile(
        company_overview="검색 포털과 커머스를 운영하는 IT 기업",
        industry_environment=["플랫폼 규제 강화 추세"],
        business_nature=["광고·커머스 중심 수익 구조"],
        financial_highlights=["2025년 매출 10조 원 (전년 대비 +8%)"],
        recent_issues=[
            IssueNote(
                issue="공정위 과징금 부과",
                detail="시장지배력 남용 관련 — 충당부채 인식 검토 필요",
                source="https://news.example.com/a1",
            )
        ],
        risk_candidates=[
            RiskCandidate(
                risk="과징금 관련 충당부채 과소계상",
                rationale="공정위 제재 진행 중이나 규모 미확정",
                affected_area="충당부채 — 완전성·평가",
                standards_query="소송과 배상청구 충당부채 감사절차",
            )
        ],
        understanding_gaps=["내부통제 구조는 공개 자료로 확인 불가"],
        overall="규제 리스크가 핵심 감사 고려사항",
    )


def test_render_profile_sections_and_citation():
    profile = _sample_profile()
    profile.risk_candidates[0].citation = "감사기준서 501 문단 9"
    profile.risk_candidates[0].citation_cid = "KSA::501::9"
    out = _render_profile(
        "네이버",
        profile,
        [{"url": "https://ko.wikipedia.org/wiki/네이버", "title": "네이버 - 위키백과"}],
        focus="최근 소송",
    )
    for section in (
        "① 기업 개관",
        "② 산업·규제 환경",
        "③ 사업의 성격",
        "④ 재무 하이라이트",
        "⑤ 최근 이슈",
        "⑥ 유의적 위험 후보",
        "⑦ 추가로 확인해야 할 이해 항목",
        "⑧ 한눈 요약",
        "조사 자료",
        "근거 목록",
    ):
        assert section in out
    assert "요청 초점: 최근 소송" in out
    assert "_영향: 충당부채 — 완전성·평가_" in out
    assert "근거: 감사기준서 501 문단 9" in out
    assert "`KSA::501::9`" in out
    assert "감사증거가 아닙니다" in out


def test_triage_fallback_heuristic():
    nodes = ProfilerNodes(model=FakeModel(), searcher=FakeSearcher(), scraper=FakeScraper())
    update = nodes.triage(
        {"messages": [HumanMessage(content="삼성전자 기업이해 브리핑을 만들어줘")]}
    )
    assert update["mode"] == "profile"

    update = nodes.triage({"messages": [HumanMessage(content="안녕?")]})
    assert update["mode"] == "chat"


def test_plan_extracts_urls_in_code_and_company_via_llm():
    model = FakeModel({ProfilePlan: ProfilePlan(company="네이버", focus="최근 소송")})
    nodes = ProfilerNodes(model=model, searcher=FakeSearcher(), scraper=FakeScraper())
    update = nodes.plan(
        {"question": "https://ko.wikipedia.org/wiki/네이버 보고 네이버 브리핑 만들어줘"}
    )
    assert update["company"] == "네이버"
    assert update["focus"] == "최근 소송"
    assert update["provided_urls"] == ["https://ko.wikipedia.org/wiki/네이버"]
    assert nodes.route_plan(update) == "dart"


def test_plan_without_company_or_url_fails_with_guidance():
    nodes = ProfilerNodes(model=FakeModel(), searcher=FakeSearcher(), scraper=FakeScraper())
    update = nodes.plan({"question": "브리핑 만들어줘"})
    assert update["error"]
    assert nodes.route_plan(update) == "fail"


def test_gather_uses_provided_urls_without_search():
    searcher = FakeSearcher(available=False)
    nodes = ProfilerNodes(model=FakeModel(), searcher=searcher, scraper=FakeScraper())
    update = nodes.gather(
        {"company": "네이버", "provided_urls": ["https://example.com/a"]}
    )
    assert update["error"] is None
    assert [s["url"] for s in update["sources"]] == ["https://example.com/a"]
    assert searcher.queries == []  # 검색 미사용


def test_gather_without_urls_and_without_key_fails_with_guidance():
    nodes = ProfilerNodes(
        model=FakeModel(), searcher=FakeSearcher(available=False), scraper=FakeScraper()
    )
    update = nodes.gather({"company": "삼성전자", "provided_urls": []})
    assert update["error"] == NO_SOURCE_MESSAGE
    assert nodes.route_gather(update) == "fail"


def test_gather_search_diversifies_domains_and_caps_sources():
    hits = [
        SearchHit(title="a", url="https://news.example.com/1", snippet="발췌1"),
        SearchHit(title="b", url="https://news.example.com/2", snippet="발췌2"),  # 같은 도메인
        SearchHit(title="c", url="https://ir.example.org/3", snippet=""),
        SearchHit(title="d", url="https://blog.example.net/4", snippet=""),
        SearchHit(title="e", url="https://extra.example.io/5", snippet=""),
    ]
    searcher = FakeSearcher(hits=hits)
    nodes = ProfilerNodes(model=FakeModel(), searcher=searcher, scraper=FakeScraper())
    update = nodes.gather({"company": "삼성전자", "provided_urls": []})
    urls = [s["url"] for s in update["sources"]]
    assert len(urls) == 4  # MAX_SOURCES 상한
    assert "https://news.example.com/2" not in urls  # 정독 대상은 도메인 중복 배제
    # 발췌는 정독 대상이 아니어도(같은 도메인이어도) 폭 보완 증거로 수집
    assert "발췌2" in update["search_snippets"]
    # 최근 이슈 질의는 news topic으로 나간다
    assert ("삼성전자 최근 이슈 소송 규제", "news") in searcher.queries


def test_extract_records_failures_and_clips():
    scraper = FakeScraper(
        results={
            "https://ok.example.com/": "가" * 10_000,
            "https://broken.example.com/": ValueError("fetch failed"),
        }
    )
    nodes = ProfilerNodes(model=FakeModel(), searcher=FakeSearcher(), scraper=scraper)
    update = nodes.extract(
        {
            "company": "네이버",
            "sources": [
                {"url": "https://ok.example.com/", "title": ""},
                {"url": "https://broken.example.com/", "title": ""},
            ],
        }
    )
    assert update["error"] is None  # 하나라도 성공하면 진행
    ok, broken = update["extracts"]
    assert len(ok["text"]) == 5_000  # MAX_EXTRACT_CHARS 클립
    assert broken["text"].startswith("(추출 실패")


def test_extract_all_failures_routes_to_fail():
    scraper = FakeScraper(results={"https://broken.example.com/": ValueError("x")})
    nodes = ProfilerNodes(model=FakeModel(), searcher=FakeSearcher(), scraper=scraper)
    update = nodes.extract(
        {
            "company": "네이버",
            "sources": [{"url": "https://broken.example.com/", "title": ""}],
        }
    )
    assert update["error"]
    assert nodes.route_extract(update) == "fail"


def test_analyze_builds_profile_from_extracts():
    model = FakeModel({CompanyProfile: _sample_profile()})
    nodes = ProfilerNodes(model=model, searcher=FakeSearcher(), scraper=FakeScraper())
    update = nodes.analyze(
        {
            "company": "네이버",
            "extracts": [{"url": "https://example.com/a", "text": "본문"}],
        }
    )
    assert update["error"] is None
    assert update["profile"]["company_overview"].startswith("검색 포털")
    assert nodes.route_analyze(update) == "cite"


def test_analyze_failure_retries_then_fails():
    nodes = ProfilerNodes(model=FakeModel(), searcher=FakeSearcher(), scraper=FakeScraper())
    state = {
        "company": "네이버",
        "extracts": [{"url": "https://example.com/a", "text": "본문"}],
    }
    update = nodes.analyze(state)
    assert update["error"] and nodes.route_analyze(update) == "retry"
    update = nodes.analyze({**state, "attempts": update["attempts"]})
    assert update["error"] and nodes.route_analyze(update) == "fail"


def test_profile_coerces_item_tagged_string_and_missing_sections():
    """Space 실측 실패 재현: 리스트 필드가 '<item>…' 문자열 + 나머지 섹션 누락."""
    profile = CompanyProfile.model_validate(
        {
            "company_overview": "개관",
            "industry_environment": "<item>메모리 경쟁 심화</item><item>규제 강화</item>",
        }
    )
    assert profile.industry_environment == ["메모리 경쟁 심화", "규제 강화"]
    assert profile.business_nature == []  # 누락 섹션은 빈 값 강등
    assert profile.overall == ""


def test_analyze_retry_includes_previous_validation_error():
    captured = {}

    class CapturingModel:
        def with_structured_output(self, _schema):
            def _invoke(messages):
                captured["system"] = messages[0].content
                return _sample_profile()

            return SimpleNamespace(invoke=_invoke)

    nodes = ProfilerNodes(
        model=CapturingModel(), searcher=FakeSearcher(), scraper=FakeScraper()
    )
    update = nodes.analyze(
        {
            "company": "네이버",
            "extracts": [{"url": "https://example.com/a", "text": "본문"}],
            "attempts": 1,
            "error": "프로파일 생성 실패 — 7 validation errors",
        }
    )
    assert update["error"] is None
    assert "직전 시도가 스키마 검증에 실패" in captured["system"]
    assert "7 validation errors" in captured["system"]


def test_profile_coerces_weak_model_strings():
    profile = CompanyProfile.model_validate(
        {
            "company_overview": "o",
            "industry_environment": [],
            "business_nature": [],
            "financial_highlights": [],
            "recent_issues": ["공정위 제재 진행"],
            "risk_candidates": ["충당부채 과소계상 위험"],
            "understanding_gaps": [],
            "overall": "s",
        }
    )
    assert profile.recent_issues[0].issue == "공정위 제재 진행"
    assert profile.risk_candidates[0].affected_area == "(미표기)"


def test_triage_decision_schema_modes():
    assert TriageDecision(mode="profile").mode == "profile"
    assert TriageDecision(mode="chat").mode == "chat"
