from __future__ import annotations

import asyncio

from prism_backend.reverse_api.signing import DouyinABogusSigner


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def test_current_web_signer_generates_fresh_long_signatures():
    async def scenario():
        async with DouyinABogusSigner() as signer:
            first = await signer.sign("aid=2906&language=zh", "need_logo=false", UA)
            second = await signer.sign("aid=2906&language=zh", "need_logo=false", UA)
            return first, second

    first, second = asyncio.run(scenario())
    assert len(first) >= 100
    assert len(second) >= 100
    assert first != second
    assert "\n" not in first


def test_signing_runtime_reuses_official_verifycenter_fingerprint():
    async def scenario():
        async with DouyinABogusSigner() as signer:
            first = await signer.sign_request("aid=2906", "", UA)
            second = await signer.sign_request("aid=2906", "", UA)
            return first, second

    first, second = asyncio.run(scenario())
    assert first["verify_fp"].startswith("verify_")
    assert len(first["verify_fp"].split("_", 2)[2]) == 36
    assert first["verify_fp"] == second["verify_fp"]
