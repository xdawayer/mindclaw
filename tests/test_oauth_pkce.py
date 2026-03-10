# input: mindclaw.oauth.pkce
# output: PKCE 生成器测试
# pos: OAuth PKCE 工具测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import base64
import hashlib

from mindclaw.oauth.pkce import generate_pkce_pair


class TestPKCE:
    def test_returns_verifier_and_challenge(self):
        verifier, challenge = generate_pkce_pair()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0

    def test_verifier_length(self):
        """RFC 7636: code_verifier is 43-128 characters."""
        verifier, _ = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_challenge_is_s256_of_verifier(self):
        """challenge = BASE64URL(SHA256(verifier))"""
        verifier, challenge = generate_pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        assert challenge == expected

    def test_each_call_unique(self):
        v1, c1 = generate_pkce_pair()
        v2, c2 = generate_pkce_pair()
        assert v1 != v2
        assert c1 != c2
