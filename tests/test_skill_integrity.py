# input: mindclaw.skills.integrity
# output: 完整性校验模块测试
# pos: 验证 SHA256、SSRF 过滤、格式校验、大小限制
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import hashlib

import pytest

from mindclaw.skills.integrity import (
    compute_sha256,
    is_safe_download_url,
    validate_skill_content,
    validate_skill_size,
)


class TestComputeSha256:
    def test_basic_hash(self):
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(content) == expected

    def test_empty_content(self):
        assert compute_sha256(b"") == hashlib.sha256(b"").hexdigest()

    def test_returns_hex_string(self):
        result = compute_sha256(b"test data")
        assert isinstance(result, str)
        assert len(result) == 64
        # Must be valid hex
        int(result, 16)

    def test_different_contents_different_hashes(self):
        assert compute_sha256(b"aaa") != compute_sha256(b"bbb")

    def test_same_content_same_hash(self):
        content = b"deterministic"
        assert compute_sha256(content) == compute_sha256(content)


class TestIsSafeDownloadUrl:
    def test_https_public_url(self):
        assert is_safe_download_url("https://example.com/skill.md") is True

    def test_http_rejected(self):
        assert is_safe_download_url("http://example.com/skill.md") is False

    def test_private_ip_192_168_rejected(self):
        assert is_safe_download_url("https://192.168.1.1/skill.md") is False

    def test_private_ip_10_rejected(self):
        assert is_safe_download_url("https://10.0.0.1/skill.md") is False

    def test_private_ip_172_16_rejected(self):
        assert is_safe_download_url("https://172.16.0.1/skill.md") is False

    def test_loopback_ipv4_rejected(self):
        assert is_safe_download_url("https://127.0.0.1/skill.md") is False

    def test_loopback_localhost_rejected(self):
        assert is_safe_download_url("https://localhost/skill.md") is False

    def test_link_local_rejected(self):
        assert is_safe_download_url("https://169.254.169.254/skill.md") is False

    def test_ftp_rejected(self):
        assert is_safe_download_url("ftp://example.com/skill.md") is False

    def test_empty_url(self):
        assert is_safe_download_url("") is False

    def test_https_github_raw_allowed(self):
        assert (
            is_safe_download_url(
                "https://raw.githubusercontent.com/user/repo/main/skill.md"
            )
            is True
        )

    def test_no_scheme_rejected(self):
        assert is_safe_download_url("example.com/skill.md") is False

    def test_url_with_port_public_allowed(self):
        # Public IP with non-standard port is still public
        assert is_safe_download_url("https://example.com:8443/skill.md") is True


class TestValidateSkillContent:
    def test_valid_skill(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test skill\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test Skill\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True
        assert result.name == "test-skill"
        assert result.description == "A test skill"

    def test_valid_skill_always_load(self):
        content = (
            "---\n"
            "name: always-skill\n"
            "description: Always loaded\n"
            "load: always\n"
            "---\n\n"
            "# Always Skill\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True
        assert result.load == "always"

    def test_missing_name(self):
        content = (
            "---\n"
            "description: A test skill\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is False
        assert "name" in result.error.lower()

    def test_no_front_matter(self):
        content = "# Just a heading\nNo front-matter."
        result = validate_skill_content(content)
        assert result.valid is False

    def test_empty_string(self):
        result = validate_skill_content("")
        assert result.valid is False

    def test_valid_with_extra_fields(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test\n"
            "load: on_demand\n"
            "version: 1.0.0\n"
            "source: github:user/repo\n"
            "sha256: abc123\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True

    def test_invalid_load_mode(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test\n"
            "load: invalid_mode\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is False
        assert "load" in result.error.lower()

    def test_result_is_frozen(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: A test\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        with pytest.raises((AttributeError, TypeError)):
            result.valid = False  # type: ignore[misc]

    def test_missing_description_defaults_empty(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "load: on_demand\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True
        assert result.description == ""

    def test_missing_load_defaults_on_demand(self):
        content = (
            "---\n"
            "name: test-skill\n"
            "description: No load field\n"
            "---\n\n"
            "# Test\n"
        )
        result = validate_skill_content(content)
        assert result.valid is True
        assert result.load == "on_demand"

    def test_invalid_result_error_is_string(self):
        result = validate_skill_content("no front matter")
        assert isinstance(result.error, str)
        assert len(result.error) > 0


class TestValidateSkillSize:
    def test_within_limit(self):
        assert validate_skill_size(b"x" * 100, max_size=8192) is True

    def test_at_limit(self):
        assert validate_skill_size(b"x" * 8192, max_size=8192) is True

    def test_over_limit(self):
        assert validate_skill_size(b"x" * 8193, max_size=8192) is False

    def test_empty(self):
        assert validate_skill_size(b"", max_size=8192) is True

    def test_custom_max_size_smaller(self):
        assert validate_skill_size(b"x" * 100, max_size=50) is False

    def test_custom_max_size_larger(self):
        assert validate_skill_size(b"x" * 8192, max_size=16384) is True

    def test_default_max_size_is_8192(self):
        assert validate_skill_size(b"x" * 8192) is True
        assert validate_skill_size(b"x" * 8193) is False
