# input: tools/base.py, patchright (lazy), asyncio, json, pathlib
# output: BossZPSearchTool
# pos: Boss直聘职位搜索工具，Patchright 反检测浏览器自动化
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import random
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

from loguru import logger

from .base import RiskLevel, Tool

# ── Constants ──────────────────────────────────────────────

_SEARCH_URL = "https://www.zhipin.com/web/geek/job"
_API_PATTERN = "wapi/zpgeek/search/joblist.json"
_LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
_LOGGED_IN_INDICATOR = "/web/geek/job"
_SESSION_EXPIRED_PATTERNS = ("/web/user/", "/web/common/security-check")

_TIMEOUT = 45
_LOGIN_POLL_INTERVAL = 2.0
_LOGIN_TIMEOUT = 180

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_CAPTCHA_SELECTORS = (
    ".geetest_panel",
    ".verify-img-panel",
    "#captcha",
    ".nc-container",
    ".slide-verify",
)

_VALID_EXPERIENCE = {"", "101", "102", "103", "104", "105", "106"}
_VALID_SALARY = {"", "402", "403", "404", "405", "406", "407"}
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_JOB_HREF_RE = re.compile(r"^/job_detail/[A-Za-z0-9_-]+\.html")

CITY_CODES: dict[str, str] = {
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "南京": "101190100",
    "武汉": "101200100",
    "西安": "101110100",
    "苏州": "101190400",
    "天津": "101030100",
    "重庆": "101040100",
    "长沙": "101250100",
    "郑州": "101180100",
    "东莞": "101281600",
    "青岛": "101120200",
    "合肥": "101220100",
    "厦门": "101230200",
    "佛山": "101280800",
    "大连": "101070200",
    "珠海": "101280700",
    "无锡": "101190200",
    "宁波": "101210400",
    "济南": "101120100",
    "福州": "101230100",
    "昆明": "101290100",
    "哈尔滨": "101050100",
    "沈阳": "101070100",
    "长春": "101060100",
    "全国": "100010000",
}

# ── Rate Limiter (inline) ─────────────────────────────────


class _RateLimiter:
    """In-memory rate limiter with per-request delay and daily cap."""

    def __init__(self, min_delay: float, max_delay: float, daily_cap: int) -> None:
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._daily_cap = daily_cap
        self._last_request: float = 0.0
        self._daily_count: int = 0
        self._counter_date: date = date.today()

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._counter_date:
            self._daily_count = 0
            self._counter_date = today

    def can_proceed(self) -> bool:
        self._reset_if_new_day()
        return self._daily_count < self._daily_cap

    def remaining_today(self) -> int:
        self._reset_if_new_day()
        return max(0, self._daily_cap - self._daily_count)

    async def wait(self) -> None:
        """Sleep for random delay since last request."""
        if self._last_request > 0:
            elapsed = time.monotonic() - self._last_request
            delay = random.uniform(self._min_delay, self._max_delay)
            remaining = delay - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request = time.monotonic()

    def record(self) -> None:
        self._reset_if_new_day()
        self._daily_count += 1


# ── Session Manager (inline) ──────────────────────────────


class _SessionManager:
    """Manages Patchright browser sessions with cookie persistence."""

    def __init__(
        self,
        session_path: Path,
        proxy: str,
        headless: bool,
        page_limit: int,
    ) -> None:
        self._session_path = session_path
        self._proxy = proxy
        self._headless = headless
        self._page_limit = page_limit
        self._pages_used: int = 0

    def is_session_valid(self) -> bool:
        """Check if saved session file exists and is recent (< 24h)."""
        if not self._session_path.exists():
            return False
        mtime = self._session_path.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        return age_hours < 24

    def needs_refresh(self) -> bool:
        """Check if we've hit the page limit and need a new context."""
        return self._pages_used >= self._page_limit

    def record_page(self) -> None:
        self._pages_used += 1

    def reset_page_counter(self) -> None:
        self._pages_used = 0

    async def create_context(self):
        """Create a new browser context with saved cookies.

        Returns (pw, browser, context) tuple. Caller must close all.
        """
        async_playwright = _import_async_playwright()
        pw = await async_playwright().start()

        launch_args = {"headless": self._headless}
        browser = await pw.chromium.launch(**launch_args)

        context_args: dict = {
            "user_agent": _DEFAULT_UA,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
        }
        if self._proxy:
            context_args["proxy"] = {"server": self._proxy}
        if self._session_path.exists():
            context_args["storage_state"] = str(self._session_path)

        context = await browser.new_context(**context_args)
        return pw, browser, context

    async def login_interactive(self) -> bool:
        """Open headed browser for user QR code login. Save cookies on success."""
        async_playwright = _import_async_playwright()
        pw = await async_playwright().start()

        try:
            browser = await pw.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent=_DEFAULT_UA,
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
            )
            page = await context.new_page()
            await page.goto(_LOGIN_URL, wait_until="domcontentloaded")

            logger.info("Waiting for user to scan QR code...")

            # Poll for login success
            elapsed = 0.0
            while elapsed < _LOGIN_TIMEOUT:
                await asyncio.sleep(_LOGIN_POLL_INTERVAL)
                elapsed += _LOGIN_POLL_INTERVAL

                url = page.url
                if (
                    _LOGGED_IN_INDICATOR in url
                    or "/web/geek/" in url
                    or "/web/boss/" in url
                    or "/web/chat/" in url
                ):
                    # Successfully logged in
                    self._session_path.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(self._session_path))
                    self._session_path.chmod(0o600)
                    logger.info(f"Session saved to {self._session_path}")
                    await browser.close()
                    await pw.stop()
                    return True

                # Also check for cookie presence
                cookies = await context.cookies("https://www.zhipin.com")
                has_token = any(c["name"] == "__zp_stoken__" for c in cookies)
                if has_token:
                    self._session_path.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(self._session_path))
                    self._session_path.chmod(0o600)
                    logger.info(f"Session saved to {self._session_path}")
                    await browser.close()
                    await pw.stop()
                    return True

            logger.warning("Login timed out")
            await browser.close()
            await pw.stop()
            return False
        except Exception as exc:
            logger.error(f"Login error: {exc}")
            try:
                await pw.stop()
            except Exception:
                pass
            return False

    @staticmethod
    def detect_session_expired(url: str) -> bool:
        """Check if current page URL indicates session expiry."""
        return any(pattern in url for pattern in _SESSION_EXPIRED_PATTERNS)


# ── Helper Functions ──────────────────────────────────────


def _import_async_playwright():
    """Lazy import patchright's async_playwright to keep it optional."""
    try:
        from patchright.async_api import async_playwright
        return async_playwright
    except ImportError:
        raise ImportError(
            "patchright is required for Boss直聘 tool. "
            "Install it with: pip install patchright && patchright install chromium"
        )


def _resolve_city(city: str) -> str:
    """Resolve city name to code. Accepts Chinese name or numeric code."""
    if city in CITY_CODES:
        return CITY_CODES[city]
    # Already a numeric code
    if city.isdigit() and len(city) == 9:
        return city
    # Fuzzy: check if city is a substring of any key
    for name, code in CITY_CODES.items():
        if city in name:
            return code
    return CITY_CODES["全国"]


def _parse_job(raw: dict) -> dict:
    """Parse a single job item from API response."""
    enc_id = raw.get("encryptJobId", "")
    job_url = (
        f"https://www.zhipin.com/job_detail/{enc_id}.html"
        if _JOB_ID_RE.match(enc_id) else ""
    )
    return {
        "job_id": enc_id,
        "title": raw.get("jobName", ""),
        "company": raw.get("brandName", ""),
        "company_size": raw.get("brandScaleName", ""),
        "industry": raw.get("brandIndustry", ""),
        "salary": raw.get("salaryDesc", ""),
        "city": raw.get("cityName", ""),
        "area": raw.get("areaDistrict", ""),
        "experience": raw.get("jobExperience", ""),
        "degree": raw.get("jobDegree", ""),
        "tags": raw.get("skills", []),
        "hr_name": raw.get("bossName", ""),
        "hr_title": raw.get("bossTitle", ""),
        "hr_online": bool(raw.get("bossOnline")),
        "job_url": job_url,
    }


def _format_jobs(jobs: list[dict], page: int, total: int, warnings: list[str]) -> str:
    """Format job list as readable text."""
    if not jobs:
        parts = ["No jobs found for this search."]
        if warnings:
            parts.append("\nWarnings: " + "; ".join(warnings))
        return "\n".join(parts)

    lines = [f"Found {total} jobs (page {page}, showing {len(jobs)}):\n"]

    for i, job in enumerate(jobs, 1):
        tags_str = ", ".join(job.get("tags", []))
        hr_status = "online" if job.get("hr_online") else "offline"
        lines.append(
            f"{i}. [{job['title']}] @ {job['company']}\n"
            f"   Salary: {job['salary']} | Location: {job['city']} {job.get('area', '')}\n"
            f"   Exp: {job['experience']} | Degree: {job['degree']}\n"
            f"   Tags: {tags_str}\n"
            f"   HR: {job['hr_name']}({job['hr_title']}, {hr_status})\n"
            f"   URL: {job['job_url']}"
        )

    if warnings:
        lines.append("\nWarnings: " + "; ".join(warnings))

    return "\n".join(lines)


async def _detect_captcha(page) -> bool:
    """Check if a captcha is present on the page."""
    for selector in _CAPTCHA_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el:
                return True
        except Exception:
            pass
    return False


# ── Main Tool ─────────────────────────────────────────────


class BossZPSearchTool(Tool):
    name = "bosszp_search"
    description = (
        "Search jobs on Boss直聘 (zhipin.com) by keyword, city, experience, salary. "
        "Requires prior login via 'mindclaw bosszp-login' command."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword (e.g. 'Python', 'product manager', 'AI engineer')",
            },
            "city": {
                "type": "string",
                "description": (
                    "City name in Chinese or code "
                    "(e.g. '北京', '上海', '深圳', '101010100'). Default: 全国"
                ),
            },
            "experience": {
                "type": "string",
                "description": (
                    "Experience filter: "
                    "'101'=no requirement, '102'=under 1 year, '103'=1-3 years, "
                    "'104'=3-5 years, '105'=5-10 years, '106'=10+ years"
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
            "page": {
                "type": "integer",
                "description": "Page number (1-10, default 1)",
            },
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 8000

    def __init__(
        self,
        session_path: Path,
        proxy: str = "",
        min_delay: float = 3.0,
        max_delay: float = 8.0,
        daily_cap: int = 100,
        page_limit: int = 4,
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
        # Validate params
        query = params.get("query", "").strip()
        if not query:
            return "Error: 'query' parameter is required"
        if len(query) > 50:
            return "Error: 'query' too long (max 50 characters)"

        city = _resolve_city(params.get("city", "全国"))

        page = params.get("page", 1)
        try:
            page = max(1, min(10, int(page)))
        except (TypeError, ValueError):
            page = 1

        experience = params.get("experience", "")
        salary = params.get("salary", "")

        if experience not in _VALID_EXPERIENCE:
            return f"Error: invalid 'experience' value '{experience}'. Valid: 101-106"
        if salary not in _VALID_SALARY:
            return f"Error: invalid 'salary' value '{salary}'. Valid: 402-407"

        # Check rate limit
        if not self._limiter.can_proceed():
            remaining = self._limiter.remaining_today()
            return f"Error: daily request cap reached ({remaining} remaining). Try again tomorrow."

        # Check session
        if not self._session.is_session_valid():
            return (
                "Error: no valid Boss直聘 session found. "
                "Run 'mindclaw bosszp-login' to login first."
            )

        # Wait for rate limit delay
        await self._limiter.wait()

        # Execute search
        try:
            result = await asyncio.wait_for(
                self._do_search(query, city, page, experience, salary),
                timeout=_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return f"Error: search timed out after {_TIMEOUT}s"
        except ImportError as exc:
            return str(exc)
        except Exception as exc:
            logger.exception("Boss直聘 search failed")
            return f"Error: search failed - {exc}"

        self._limiter.record()
        return result

    async def _do_search(
        self,
        query: str,
        city: str,
        page: int,
        experience: str,
        salary: str,
    ) -> str:
        """Execute the actual browser-based search."""
        warnings: list[str] = []

        # Check if session needs refresh (page limit)
        if self._session.needs_refresh():
            self._session.reset_page_counter()

        pw, browser, context = await self._session.create_context()

        try:
            pg = await context.new_page()

            # Build search URL
            url_params = f"query={quote(query)}&city={city}&page={page}"
            if experience:
                url_params += f"&experience={experience}"
            if salary:
                url_params += f"&salary={salary}"
            search_url = f"{_SEARCH_URL}?{url_params}"

            # Strategy A: Intercept XHR response
            api_response: dict = {}
            api_captured = asyncio.Event()

            async def handle_response(response):
                nonlocal api_response
                if _API_PATTERN in response.url:
                    try:
                        body = await response.json()
                        api_response = body
                        api_captured.set()
                    except Exception:
                        pass

            pg.on("response", handle_response)

            await pg.goto(search_url, wait_until="domcontentloaded")

            # Check session expiry
            if _SessionManager.detect_session_expired(pg.url):
                return (
                    "Error: Boss直聘 session expired. "
                    "Run 'mindclaw bosszp-login' to re-login."
                )

            # Check for captcha
            if await _detect_captcha(pg):
                warnings.append("captcha detected - results may be incomplete")

            # Wait for API response (up to 15s)
            try:
                await asyncio.wait_for(api_captured.wait(), timeout=15)
            except asyncio.TimeoutError:
                # Strategy B: Fall back to DOM parsing
                logger.warning("XHR interception timed out, falling back to DOM parsing")
                warnings.append("XHR interception failed, using DOM fallback")
                return await self._parse_dom_fallback(pg, page, warnings)

            # Parse API response
            zp_data = api_response.get("zpData", {})
            job_list = zp_data.get("jobList", [])
            total = zp_data.get("totalCount", 0) if zp_data.get("totalCount") else len(job_list)
            has_more = zp_data.get("hasMore", False)

            jobs = [_parse_job(raw) for raw in job_list]

            self._session.record_page()

            result = _format_jobs(jobs, page, total, warnings)
            if has_more:
                result += f"\n\n[Has more results - use page={page + 1} to see next page]"

            if self.max_result_chars and len(result) > self.max_result_chars:
                result = result[: self.max_result_chars] + "\n[truncated]"

            return result

        finally:
            await context.close()
            await browser.close()
            await pw.stop()

    async def _parse_dom_fallback(self, page, page_num: int, warnings: list[str]) -> str:
        """Fallback: parse job cards from DOM when XHR interception fails."""
        jobs: list[dict] = []

        try:
            # Wait for job cards to render
            await page.wait_for_selector(".job-card-wrapper", timeout=10000)
            cards = await page.query_selector_all(".job-card-wrapper")

            for card in cards:
                try:
                    title_el = await card.query_selector(".job-name")
                    company_el = await card.query_selector(".company-name a")
                    salary_el = await card.query_selector(".salary")
                    area_el = await card.query_selector(".job-area")
                    tags_els = await card.query_selector_all(".tag-list li")
                    hr_el = await card.query_selector(".info-public em")
                    link_el = await card.query_selector("a.job-card-left")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    salary_text = await salary_el.inner_text() if salary_el else ""
                    area = await area_el.inner_text() if area_el else ""
                    hr_name = await hr_el.inner_text() if hr_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""

                    tags = []
                    for tag_el in tags_els:
                        tags.append(await tag_el.inner_text())

                    job_url = (
                        f"https://www.zhipin.com{href}"
                        if href and _JOB_HREF_RE.match(href) else ""
                    )

                    jobs.append({
                        "title": title.strip(),
                        "company": company.strip(),
                        "salary": salary_text.strip(),
                        "city": area.strip(),
                        "area": "",
                        "experience": "",
                        "degree": "",
                        "tags": tags,
                        "hr_name": hr_name.strip(),
                        "hr_title": "",
                        "hr_online": False,
                        "job_url": job_url,
                        "job_id": "",
                        "company_size": "",
                        "industry": "",
                    })
                except Exception:
                    continue

        except Exception as exc:
            logger.warning(f"DOM parsing error: {exc}")
            warnings.append("DOM parsing error: see logs for details")

        return _format_jobs(jobs, page_num, len(jobs), warnings)
