# input: mindclaw/tools/bosszp.py, mindclaw/config/schema.py
# output: Tests for BossZP tool
# pos: Boss直聘工具单元测试 + 集成测试

import time
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.config.schema import BossZPConfig
from mindclaw.tools.bosszp import (
    CITY_CODES,
    BossZPSearchTool,
    _format_jobs,
    _parse_job,
    _RateLimiter,
    _resolve_city,
    _SessionManager,
)

# ── City Resolution ───────────────────────────────────────


class TestResolveCity:
    def test_exact_name(self):
        assert _resolve_city("北京") == "101010100"
        assert _resolve_city("深圳") == "101280600"

    def test_numeric_code(self):
        assert _resolve_city("101010100") == "101010100"

    def test_substring_match(self):
        assert _resolve_city("哈尔") == "101050100"  # matches 哈尔滨

    def test_unknown_defaults_to_quanguo(self):
        assert _resolve_city("火星") == CITY_CODES["全国"]

    def test_quanguo(self):
        assert _resolve_city("全国") == "100010000"


# ── Job Parsing ───────────────────────────────────────────


class TestParseJob:
    def test_parse_full_job(self):
        raw = {
            "encryptJobId": "abc123",
            "jobName": "Python Developer",
            "brandName": "TestCorp",
            "brandScaleName": "100-499",
            "brandIndustry": "Internet",
            "salaryDesc": "25-50K",
            "cityName": "Beijing",
            "areaDistrict": "Haidian",
            "jobExperience": "3-5 years",
            "jobDegree": "Bachelor",
            "skills": ["Python", "Django"],
            "bossName": "Zhang",
            "bossTitle": "CTO",
            "bossOnline": True,
        }
        job = _parse_job(raw)
        assert job["job_id"] == "abc123"
        assert job["title"] == "Python Developer"
        assert job["company"] == "TestCorp"
        assert job["salary"] == "25-50K"
        assert job["tags"] == ["Python", "Django"]
        assert job["hr_online"] is True
        assert "abc123" in job["job_url"]

    def test_parse_missing_fields(self):
        job = _parse_job({})
        assert job["job_id"] == ""
        assert job["title"] == ""
        assert job["tags"] == []
        assert job["hr_online"] is False


# ── Format Jobs ───────────────────────────────────────────


class TestFormatJobs:
    def test_format_empty(self):
        result = _format_jobs([], 1, 0, [])
        assert "No jobs found" in result

    def test_format_with_warnings(self):
        result = _format_jobs([], 1, 0, ["captcha detected"])
        assert "captcha detected" in result

    def test_format_jobs_list(self):
        jobs = [
            {
                "title": "Python Dev",
                "company": "Corp",
                "salary": "20K",
                "city": "BJ",
                "area": "HD",
                "experience": "3y",
                "degree": "BS",
                "tags": ["Python"],
                "hr_name": "HR",
                "hr_title": "Manager",
                "hr_online": True,
                "job_url": "https://example.com",
            }
        ]
        result = _format_jobs(jobs, 1, 1, [])
        assert "Python Dev" in result
        assert "Corp" in result
        assert "20K" in result
        assert "online" in result


# ── Rate Limiter ──────────────────────────────────────────


class TestRateLimiter:
    def test_can_proceed_under_cap(self):
        limiter = _RateLimiter(min_delay=0.0, max_delay=0.0, daily_cap=5)
        assert limiter.can_proceed() is True

    def test_can_proceed_at_cap(self):
        limiter = _RateLimiter(min_delay=0.0, max_delay=0.0, daily_cap=2)
        limiter.record()
        limiter.record()
        assert limiter.can_proceed() is False

    def test_remaining_today(self):
        limiter = _RateLimiter(min_delay=0.0, max_delay=0.0, daily_cap=10)
        limiter.record()
        limiter.record()
        limiter.record()
        assert limiter.remaining_today() == 7

    def test_date_rollover_resets(self):
        limiter = _RateLimiter(min_delay=0.0, max_delay=0.0, daily_cap=2)
        limiter.record()
        limiter.record()
        assert limiter.can_proceed() is False
        # Simulate date change
        limiter._counter_date = date(2020, 1, 1)
        assert limiter.can_proceed() is True
        assert limiter.remaining_today() == 2

    @pytest.mark.asyncio
    async def test_wait_applies_delay(self):
        limiter = _RateLimiter(min_delay=0.05, max_delay=0.05, daily_cap=100)
        # First call skips delay (no previous request)
        await limiter.wait()
        # Second call should apply delay
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.04  # small tolerance


# ── Session Manager ───────────────────────────────────────


class TestSessionManager:
    def test_is_session_valid_no_file(self, tmp_path):
        mgr = _SessionManager(
            session_path=tmp_path / "nonexistent.json",
            proxy="",
            headless=True,
            page_limit=4,
        )
        assert mgr.is_session_valid() is False

    def test_is_session_valid_recent_file(self, tmp_path):
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")
        mgr = _SessionManager(
            session_path=session_file,
            proxy="",
            headless=True,
            page_limit=4,
        )
        assert mgr.is_session_valid() is True

    def test_page_limit_tracking(self, tmp_path):
        mgr = _SessionManager(
            session_path=tmp_path / "s.json",
            proxy="",
            headless=True,
            page_limit=3,
        )
        assert mgr.needs_refresh() is False
        mgr.record_page()
        mgr.record_page()
        mgr.record_page()
        assert mgr.needs_refresh() is True
        mgr.reset_page_counter()
        assert mgr.needs_refresh() is False

    def test_detect_session_expired(self):
        login_url = "https://www.zhipin.com/web/user/?ka=header-login"
        job_url = "https://www.zhipin.com/web/geek/job"
        check_url = "https://www.zhipin.com/web/common/security-check"
        assert _SessionManager.detect_session_expired(login_url) is True
        assert _SessionManager.detect_session_expired(job_url) is False
        assert _SessionManager.detect_session_expired(check_url) is True


# ── Config ────────────────────────────────────────────────


class TestBossZPConfig:
    def test_defaults(self):
        cfg = BossZPConfig()
        assert cfg.enabled is False
        assert cfg.min_delay == 3.0
        assert cfg.max_delay == 8.0
        assert cfg.daily_cap == 100
        assert cfg.page_limit == 4
        assert cfg.headless is True

    def test_from_alias(self):
        cfg = BossZPConfig(**{
            "enabled": True,
            "sessionPath": "/tmp/sess.json",
            "minDelay": 1.0,
            "maxDelay": 5.0,
            "dailyCap": 50,
            "pageLimit": 3,
        })
        assert cfg.enabled is True
        assert cfg.session_path == "/tmp/sess.json"
        assert cfg.min_delay == 1.0
        assert cfg.daily_cap == 50
        assert cfg.page_limit == 3


# ── Tool Execute (integration with mocks) ─────────────────


class TestBossZPSearchTool:
    def _make_tool(self, tmp_path, session_exists=True):
        session_file = tmp_path / "bosszp_session.json"
        if session_exists:
            session_file.write_text("{}")
        return BossZPSearchTool(
            session_path=session_file,
            proxy="",
            min_delay=0.0,
            max_delay=0.0,
            daily_cap=100,
            page_limit=4,
            headless=True,
        )

    @pytest.mark.asyncio
    async def test_empty_query_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        result = await tool.execute({"query": ""})
        assert "Error" in result
        assert "required" in result

    @pytest.mark.asyncio
    async def test_long_query_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        result = await tool.execute({"query": "x" * 51})
        assert "Error" in result
        assert "too long" in result

    @pytest.mark.asyncio
    async def test_no_session_error(self, tmp_path):
        tool = self._make_tool(tmp_path, session_exists=False)
        result = await tool.execute({"query": "Python"})
        assert "Error" in result
        assert "bosszp-login" in result

    @pytest.mark.asyncio
    async def test_daily_cap_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        tool._limiter = _RateLimiter(min_delay=0, max_delay=0, daily_cap=0)
        result = await tool.execute({"query": "Python"})
        assert "Error" in result
        assert "cap" in result

    @pytest.mark.asyncio
    async def test_patchright_import_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        with patch(
            "mindclaw.tools.bosszp._import_patchright",
            side_effect=ImportError("patchright not installed"),
        ):
            result = await tool.execute({"query": "Python"})
            assert "patchright" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_page_param_clamped(self, tmp_path):
        tool = self._make_tool(tmp_path)
        # Test that page is clamped properly (no actual browser call)
        with patch.object(tool, "_do_search", new_callable=AsyncMock, return_value="ok"):
            await tool.execute({"query": "test", "page": 20})
            # _do_search should be called with page=10 (clamped)
            call_args = tool._do_search.call_args
            assert call_args[0][2] == 10  # page arg

    @pytest.mark.asyncio
    async def test_successful_search_mock(self, tmp_path):
        tool = self._make_tool(tmp_path)
        mock_result = "Found 1 jobs (page 1, showing 1):\n1. [Python Dev]"
        with patch.object(tool, "_do_search", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute({"query": "Python", "city": "北京"})
            assert "Python Dev" in result
