# input: tools/base.py, tools/bosszp.py (shared session/rate limiter), patchright (lazy)
# output: BossZPTalentSearchTool
# pos: Boss直聘招聘端人才搜索工具，浏览推荐牛人/搜索人才页面
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import re
from pathlib import Path
from urllib.parse import quote

from loguru import logger

from .base import RiskLevel, Tool
from .bosszp import (
    _RateLimiter,
    _resolve_city,
    _SessionManager,
)

# ── Constants ──────────────────────────────────────────────

_RECOMMEND_URL = "https://www.zhipin.com/web/boss/recommend"
_SEARCH_URL = "https://www.zhipin.com/web/boss/search/geek"
_REC_API_PATTERN = "wapi/zpjob/rec/geek/list"
_SEARCH_API_PATTERN = "wapi/zpboss"
_JOB_LIST_API = "wapi/zpjob/job/data/list"

_TIMEOUT = 60
_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_GEEK_NAME_RE = re.compile(r"^[\u4e00-\u9fff\w\s·.·\-]{1,20}$")

# ── Candidate Parsing ─────────────────────────────────────


def _parse_candidate(raw: dict) -> dict:
    """Parse a candidate from the recommend/search API response."""
    card = raw.get("geekCard", raw)
    edu = card.get("geekEdu", {})

    name = card.get("geekName", "")
    return {
        "name": name if _GEEK_NAME_RE.match(name) else name[:10],
        "encrypt_id": raw.get("encryptGeekId", ""),
        "work_years": card.get("geekWorkYear", ""),
        "degree": card.get("geekDegree", ""),
        "age": card.get("ageDesc", ""),
        "school": edu.get("school", ""),
        "salary_expect": card.get("salary", ""),
        "low_salary": card.get("lowSalary", 0),
        "high_salary": card.get("highSalary", 0),
        "location": card.get("expectLocationName", ""),
        "status": card.get("applyStatusDesc", ""),
        "active_time": raw.get("activeTimeDesc", ""),
        "is_friend": raw.get("isFriend", 0),
    }


def _format_candidates(
    candidates: list[dict],
    jd_summary: str,
    warnings: list[str],
) -> str:
    """Format candidate list as readable text for LLM scoring."""
    if not candidates:
        parts = ["No candidates found matching the criteria."]
        if warnings:
            parts.append("\nWarnings: " + "; ".join(warnings))
        return "\n".join(parts)

    lines = [
        f"Found {len(candidates)} candidates.\n",
        f"JD Summary: {jd_summary}\n",
    ]

    for i, c in enumerate(candidates, 1):
        salary_str = c.get("salary_expect", "")
        status = c.get("status", "")
        active = c.get("active_time", "")
        contacted = " [already contacted]" if c.get("is_friend") else ""

        lines.append(
            f"{i}. {c['name']}{contacted}\n"
            f"   Experience: {c['work_years']} | Degree: {c['degree']}"
            f" | Age: {c['age']}\n"
            f"   School: {c['school']}\n"
            f"   Expected Salary: {salary_str}\n"
            f"   Location: {c['location']} | Status: {status}\n"
            f"   Active: {active}"
        )

    if warnings:
        lines.append("\nWarnings: " + "; ".join(warnings))

    return "\n".join(lines)


# ── Main Tool ─────────────────────────────────────────────


class BossZPTalentSearchTool(Tool):
    name = "bosszp_talent_search"
    description = (
        "Search candidates on Boss直聘 recruiter side (推荐牛人/搜索人才). "
        "Returns candidate profiles for LLM scoring against a JD. "
        "Requires recruiter account login via 'mindclaw bosszp-login'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search keyword for talent (e.g. '系统策划', 'Python工程师'). "
                    "Leave empty to use recommended candidates for your posted job."
                ),
            },
            "city": {
                "type": "string",
                "description": "City name or code (e.g. '广州', '北京'). Default: 全国",
            },
            "experience": {
                "type": "string",
                "description": (
                    "Experience filter: "
                    "'101'=no req, '102'=<1yr, '103'=1-3yr, "
                    "'104'=3-5yr, '105'=5-10yr, '106'=10yr+"
                ),
            },
            "salary": {
                "type": "string",
                "description": (
                    "Salary filter: "
                    "'402'=3-5K, '403'=5-10K, '404'=10-15K, "
                    "'405'=15-25K, '406'=25-50K, '407'=50K+"
                ),
            },
            "degree": {
                "type": "string",
                "description": "'209'=highschool, '208'=college, '206'=bachelor, '202'=master",
            },
            "jd_summary": {
                "type": "string",
                "description": "Brief JD summary for context (helps with result formatting)",
            },
            "page": {
                "type": "integer",
                "description": "Page number (1-3, default 1). Keep low to avoid detection.",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 10000

    _VALID_EXPERIENCE = {"", "101", "102", "103", "104", "105", "106"}
    _VALID_SALARY = {"", "402", "403", "404", "405", "406", "407"}
    _VALID_DEGREE = {"", "209", "208", "206", "202"}

    def __init__(
        self,
        session_path: Path,
        proxy: str = "",
        min_delay: float = 5.0,
        max_delay: float = 10.0,
        daily_cap: int = 30,
        page_limit: int = 3,
        headless: bool = True,
    ) -> None:
        self._session = _SessionManager(
            session_path=session_path,
            proxy=proxy,
            headless=headless,
            page_limit=page_limit,
        )
        self._limiter = _RateLimiter(
            min_delay=min_delay,
            max_delay=max_delay,
            daily_cap=daily_cap,
        )

    async def execute(self, params: dict) -> str:
        query = params.get("query", "").strip()
        if query and len(query) > 50:
            return "Error: 'query' too long (max 50 characters)"

        city = _resolve_city(params.get("city", "全国"))
        jd_summary = params.get("jd_summary", "")

        experience = params.get("experience", "")
        salary = params.get("salary", "")
        degree = params.get("degree", "")

        if experience not in self._VALID_EXPERIENCE:
            return "Error: invalid 'experience' value. Valid: 101-106"
        if salary not in self._VALID_SALARY:
            return "Error: invalid 'salary' value. Valid: 402-407"
        if degree not in self._VALID_DEGREE:
            return "Error: invalid 'degree' value. Valid: 209,208,206,202"

        page = params.get("page", 1)
        try:
            page = max(1, min(3, int(page)))
        except (TypeError, ValueError):
            page = 1

        if not self._limiter.can_proceed():
            return "Error: daily talent search cap reached. Try again tomorrow."

        if not self._session.is_session_valid():
            return (
                "Error: no valid Boss直聘 session. "
                "Run 'mindclaw bosszp-login' to login first."
            )

        await self._limiter.wait()

        try:
            result = await asyncio.wait_for(
                self._do_search(query, city, page, experience, salary, degree, jd_summary),
                timeout=_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return f"Error: talent search timed out after {_TIMEOUT}s"
        except ImportError as exc:
            return str(exc)
        except Exception as exc:
            logger.exception("Boss直聘 talent search failed")
            return f"Error: talent search failed - {exc}"

        self._limiter.record()
        return result

    async def _do_search(
        self,
        query: str,
        city: str,
        page: int,
        experience: str,
        salary: str,
        degree: str,
        jd_summary: str,
    ) -> str:
        """Execute browser-based talent search on recruiter side."""
        warnings: list[str] = []

        if self._session.needs_refresh():
            self._session.reset_page_counter()

        pw, browser, context = await self._session.create_context()

        try:
            pg = await context.new_page()

            # Decide: search mode vs recommend mode
            if query:
                return await self._search_mode(
                    pg, query, city, page, experience, salary, degree,
                    jd_summary, warnings,
                )
            else:
                return await self._recommend_mode(
                    pg, page, experience, salary, degree,
                    jd_summary, warnings,
                )
        finally:
            await context.close()
            await browser.close()
            await pw.stop()

    async def _search_mode(
        self, pg, query, city, page, experience, salary, degree,
        jd_summary, warnings,
    ) -> str:
        """Search talent by keyword on /web/boss/search/geek."""
        url_params = f"query={quote(query)}&city={city}&page={page}"
        if experience:
            url_params += f"&experience={experience}"
        if salary:
            url_params += f"&salary={salary}"
        if degree:
            url_params += f"&degree={degree}"

        search_url = f"{_SEARCH_URL}?{url_params}"

        # XHR interception
        api_response: dict = {}
        api_captured = asyncio.Event()

        async def handle_response(response):
            nonlocal api_response
            url = response.url
            if _REC_API_PATTERN in url or _SEARCH_API_PATTERN in url:
                try:
                    body = await response.json()
                    if body.get("zpData", {}).get("geekList"):
                        api_response = body
                        api_captured.set()
                except Exception:
                    pass

        pg.on("response", handle_response)
        await pg.goto(search_url, wait_until="domcontentloaded")

        # Check if redirected to login
        if "/web/user/" in pg.url:
            return (
                "Error: session expired or not a recruiter account. "
                "Run 'mindclaw bosszp-login' with a recruiter account."
            )

        # Wait for API response
        try:
            await asyncio.wait_for(api_captured.wait(), timeout=20)
        except asyncio.TimeoutError:
            warnings.append("XHR interception timed out, trying DOM fallback")
            return await self._dom_fallback(pg, jd_summary, warnings)

        return self._parse_api_response(api_response, jd_summary, warnings)

    async def _recommend_mode(
        self, pg, page, experience, salary, degree,
        jd_summary, warnings,
    ) -> str:
        """Get recommended candidates from /web/boss/recommend."""
        api_response: dict = {}
        api_captured = asyncio.Event()

        async def handle_response(response):
            nonlocal api_response
            if _REC_API_PATTERN in response.url:
                try:
                    body = await response.json()
                    if body.get("zpData", {}).get("geekList"):
                        api_response = body
                        api_captured.set()
                except Exception:
                    pass

        pg.on("response", handle_response)
        await pg.goto(_RECOMMEND_URL, wait_until="domcontentloaded")

        if "/web/user/" in pg.url:
            return (
                "Error: session expired or not a recruiter account. "
                "Run 'mindclaw bosszp-login' with a recruiter account."
            )

        # Wait for recommend API
        try:
            await asyncio.wait_for(api_captured.wait(), timeout=20)
        except asyncio.TimeoutError:
            warnings.append("Recommend API not captured, page may require iframe interaction")
            return _format_candidates([], jd_summary, warnings)

        return self._parse_api_response(api_response, jd_summary, warnings)

    def _parse_api_response(
        self, api_response: dict, jd_summary: str, warnings: list[str],
    ) -> str:
        """Parse API response into formatted candidate list."""
        zp_data = api_response.get("zpData", {})
        geek_list = zp_data.get("geekList", [])

        candidates = [_parse_candidate(raw) for raw in geek_list]

        self._session.record_page()

        result = _format_candidates(candidates, jd_summary, warnings)
        if self.max_result_chars and len(result) > self.max_result_chars:
            result = result[: self.max_result_chars] + "\n[truncated]"
        return result

    async def _dom_fallback(self, pg, jd_summary: str, warnings: list[str]) -> str:
        """Fallback: parse candidate cards from DOM."""
        candidates: list[dict] = []

        try:
            await pg.wait_for_selector(".geek-list, .recommend-card-list", timeout=10000)

            # Try search page selectors first
            cards = await pg.query_selector_all(".geek-item")
            if not cards:
                # Try recommend page selectors (may be in iframe)
                iframe_el = await pg.query_selector('iframe[name="recommendFrame"]')
                if iframe_el:
                    frame = await iframe_el.content_frame()
                    if frame:
                        cards = await frame.query_selector_all("ul.card-list > li")

            for card in cards:
                try:
                    name_el = await card.query_selector(".geek-name, .name")
                    job_el = await card.query_selector(".geek-job")
                    company_el = await card.query_selector(".geek-company")
                    active_el = await card.query_selector(".geek-active-time")

                    name = await name_el.inner_text() if name_el else ""
                    job = await job_el.inner_text() if job_el else ""
                    _ = await company_el.inner_text() if company_el else ""
                    active = await active_el.inner_text() if active_el else ""

                    candidates.append({
                        "name": name.strip()[:10],
                        "encrypt_id": "",
                        "work_years": "",
                        "degree": "",
                        "age": "",
                        "school": "",
                        "salary_expect": "",
                        "low_salary": 0,
                        "high_salary": 0,
                        "location": "",
                        "status": job.strip(),
                        "active_time": active.strip(),
                        "is_friend": 0,
                    })
                except Exception:
                    continue

        except Exception as exc:
            logger.warning(f"Talent DOM parsing error: {exc}")
            warnings.append("DOM parsing error: see logs for details")

        return _format_candidates(candidates, jd_summary, warnings)
