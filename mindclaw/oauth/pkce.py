# input: secrets, hashlib, base64
# output: 导出 generate_pkce_pair()
# pos: PKCE (Proof Key for Code Exchange) 工具，用于 OAuth 2.0 安全授权
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import base64
import hashlib
import secrets


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256).

    Returns:
        (code_verifier, code_challenge) tuple.
    """
    verifier = secrets.token_urlsafe(64)[:96]  # 96 chars, within 43-128 range
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge
