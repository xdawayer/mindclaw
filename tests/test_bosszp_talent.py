# input: mindclaw/tools/bosszp_talent.py, mindclaw/config/schema.py
# output: Tests for BossZP talent search tool
# pos: Boss直聘人才搜索工具单元测试

from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.config.schema import BossZPTalentConfig
from mindclaw.tools.bosszp import _RateLimiter
from mindclaw.tools.bosszp_talent import (
    BossZPTalentSearchTool,
    _format_candidates,
    _parse_candidate,
)

# ── Candidate Parsing ────────────────────────────────────


class TestParseCandidate:
    def test_parse_full_candidate(self):
        raw = {
            "geekCard": {
                "geekName": "张三",
                "geekWorkYear": "3-5年",
                "geekDegree": "本科",
                "ageDesc": "25-30",
                "geekEdu": {"school": "清华大学"},
                "salary": "20-30K",
                "lowSalary": 20,
                "highSalary": 30,
                "expectLocationName": "广州",
                "applyStatusDesc": "在职-考虑机会",
            },
            "encryptGeekId": "enc_abc123",
            "activeTimeDesc": "3小时前活跃",
            "isFriend": 0,
        }
        c = _parse_candidate(raw)
        assert c["name"] == "张三"
        assert c["encrypt_id"] == "enc_abc123"
        assert c["work_years"] == "3-5年"
        assert c["degree"] == "本科"
        assert c["age"] == "25-30"
        assert c["school"] == "清华大学"
        assert c["salary_expect"] == "20-30K"
        assert c["low_salary"] == 20
        assert c["high_salary"] == 30
        assert c["location"] == "广州"
        assert c["status"] == "在职-考虑机会"
        assert c["active_time"] == "3小时前活跃"
        assert c["is_friend"] == 0

    def test_parse_missing_fields(self):
        c = _parse_candidate({})
        assert c["name"] == ""
        assert c["encrypt_id"] == ""
        assert c["work_years"] == ""
        assert c["school"] == ""
        assert c["low_salary"] == 0
        assert c["is_friend"] == 0

    def test_parse_flat_structure(self):
        """Some API responses have fields at root level instead of geekCard."""
        raw = {
            "geekName": "李四",
            "geekWorkYear": "1-3年",
            "geekDegree": "硕士",
            "geekEdu": {"school": "北大"},
            "encryptGeekId": "enc_def456",
            "activeTimeDesc": "刚刚活跃",
            "isFriend": 1,
        }
        c = _parse_candidate(raw)
        assert c["name"] == "李四"
        assert c["work_years"] == "1-3年"
        assert c["school"] == "北大"
        assert c["is_friend"] == 1

    def test_long_name_truncated(self):
        raw = {"geekName": "A" * 30, "geekCard": {"geekName": "A" * 30}}
        c = _parse_candidate(raw)
        assert len(c["name"]) <= 10


# ── Format Candidates ────────────────────────────────────


class TestFormatCandidates:
    def test_format_empty(self):
        result = _format_candidates([], "系统策划", [])
        assert "No candidates found" in result

    def test_format_with_warnings(self):
        result = _format_candidates([], "", ["XHR timeout"])
        assert "XHR timeout" in result

    def test_format_candidates_list(self):
        candidates = [
            {
                "name": "王五",
                "encrypt_id": "enc_1",
                "work_years": "5-10年",
                "degree": "本科",
                "age": "30-35",
                "school": "浙大",
                "salary_expect": "30-50K",
                "low_salary": 30,
                "high_salary": 50,
                "location": "广州",
                "status": "在职-考虑机会",
                "active_time": "今日活跃",
                "is_friend": 0,
            }
        ]
        result = _format_candidates(candidates, "MMO系统策划", [])
        assert "Found 1 candidates" in result
        assert "王五" in result
        assert "5-10年" in result
        assert "浙大" in result
        assert "30-50K" in result
        assert "MMO系统策划" in result

    def test_format_contacted_flag(self):
        candidates = [
            {
                "name": "赵六",
                "encrypt_id": "",
                "work_years": "",
                "degree": "",
                "age": "",
                "school": "",
                "salary_expect": "",
                "low_salary": 0,
                "high_salary": 0,
                "location": "",
                "status": "",
                "active_time": "",
                "is_friend": 1,
            }
        ]
        result = _format_candidates(candidates, "", [])
        assert "[already contacted]" in result


# ── Config ───────────────────────────────────────────────


class TestBossZPTalentConfig:
    def test_defaults(self):
        cfg = BossZPTalentConfig()
        assert cfg.enabled is False
        assert cfg.min_delay == 5.0
        assert cfg.max_delay == 10.0
        assert cfg.daily_cap == 30
        assert cfg.page_limit == 3
        assert cfg.headless is True

    def test_from_alias(self):
        cfg = BossZPTalentConfig(**{
            "enabled": True,
            "sessionPath": "/tmp/talent_sess.json",
            "minDelay": 6.0,
            "maxDelay": 12.0,
            "dailyCap": 20,
            "pageLimit": 2,
        })
        assert cfg.enabled is True
        assert cfg.session_path == "/tmp/talent_sess.json"
        assert cfg.min_delay == 6.0
        assert cfg.daily_cap == 20
        assert cfg.page_limit == 2


# ── Tool Execute (integration with mocks) ────────────────


class TestBossZPTalentSearchTool:
    def _make_tool(self, tmp_path, session_exists=True):
        session_file = tmp_path / "talent_session.json"
        if session_exists:
            session_file.write_text("{}")
        return BossZPTalentSearchTool(
            session_path=session_file,
            proxy="",
            min_delay=0.0,
            max_delay=0.0,
            daily_cap=30,
            page_limit=3,
            headless=True,
        )

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
    async def test_invalid_experience_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        result = await tool.execute({"query": "test", "experience": "999"})
        assert "Error" in result
        assert "experience" in result

    @pytest.mark.asyncio
    async def test_invalid_salary_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        result = await tool.execute({"query": "test", "salary": "999"})
        assert "Error" in result
        assert "salary" in result

    @pytest.mark.asyncio
    async def test_invalid_degree_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        result = await tool.execute({"query": "test", "degree": "999"})
        assert "Error" in result
        assert "degree" in result

    @pytest.mark.asyncio
    async def test_page_clamped(self, tmp_path):
        tool = self._make_tool(tmp_path)
        with patch.object(tool, "_do_search", new_callable=AsyncMock, return_value="ok"):
            await tool.execute({"query": "test", "page": 20})
            call_args = tool._do_search.call_args
            assert call_args[0][2] == 3  # page clamped to 3 (not 10 like job search)

    @pytest.mark.asyncio
    async def test_empty_query_uses_recommend_mode(self, tmp_path):
        tool = self._make_tool(tmp_path)
        with patch.object(tool, "_do_search", new_callable=AsyncMock, return_value="ok"):
            await tool.execute({})
            call_args = tool._do_search.call_args
            assert call_args[0][0] == ""  # empty query = recommend mode

    @pytest.mark.asyncio
    async def test_successful_search_mock(self, tmp_path):
        tool = self._make_tool(tmp_path)
        mock_result = "Found 3 candidates.\n1. 张三\n2. 李四\n3. 王五"
        with patch.object(tool, "_do_search", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute({"query": "系统策划", "city": "广州"})
            assert "张三" in result

    @pytest.mark.asyncio
    async def test_patchright_import_error(self, tmp_path):
        tool = self._make_tool(tmp_path)
        with patch(
            "mindclaw.tools.bosszp._import_async_playwright",
            side_effect=ImportError("patchright not installed"),
        ):
            result = await tool.execute({"query": "test"})
            assert "patchright" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self, tmp_path):
        tool = self._make_tool(tmp_path)

        async def slow_search(*args, **kwargs):
            import asyncio
            await asyncio.sleep(100)

        with patch.object(tool, "_do_search", side_effect=slow_search):
            # Override timeout to be very short
            import mindclaw.tools.bosszp_talent as talent_mod
            original_timeout = talent_mod._TIMEOUT
            talent_mod._TIMEOUT = 0.01
            try:
                result = await tool.execute({"query": "test"})
                assert "Error" in result
                assert "timed out" in result
            finally:
                talent_mod._TIMEOUT = original_timeout

    def test_parse_api_response(self, tmp_path):
        tool = self._make_tool(tmp_path)
        api_response = {
            "zpData": {
                "geekList": [
                    {
                        "geekCard": {
                            "geekName": "测试候选人",
                            "geekWorkYear": "3-5年",
                            "geekDegree": "本科",
                            "ageDesc": "28",
                            "geekEdu": {"school": "MIT"},
                            "salary": "25-35K",
                            "lowSalary": 25,
                            "highSalary": 35,
                            "expectLocationName": "广州",
                            "applyStatusDesc": "在职",
                        },
                        "encryptGeekId": "enc_test",
                        "activeTimeDesc": "今日活跃",
                        "isFriend": 0,
                    }
                ]
            }
        }
        result = tool._parse_api_response(api_response, "系统策划", [])
        assert "测试候选人" in result
        assert "3-5年" in result
        assert "MIT" in result
