# Prism Reverse API (experimental)

This package records and implements internal creator-platform protocols only
for accounts the operator is authorized to use.

## Safety rules

- Never commit cookies, tokens, device identifiers, signatures, raw HAR files,
  request bodies, account identifiers, proxy addresses, or browser profiles.
- Capture only endpoint metadata and sanitized request/response *shapes*.
- Keep live session material in Prism's existing local runtime stores.
- A successful HTTP response is only `accepted`; confirm the resulting post by
  status/list API or browser before setting a publish task to `succeeded`.
- Do not automate CAPTCHAs, verification challenges, or access-control bypasses.

## Capture workflow

1. Open an already-authenticated creator page in Chrome.
2. Attach the CDP network observer before performing the action.
3. Record method, host/path, status, content type and JSON key structure.
4. Run every record through `sanitize_exchange` before saving it under
   `captures/sanitized/` (which contains no replayable credentials).
5. Convert confirmed operations into a platform adapter. Browser automation
   remains the fallback for login and human verification.

The platform host registry lives in `protocols.py`. Endpoint paths are not
guessed: they are added only after an authorized, observed request is tested.

QR-login protocol metadata and its normalized state machine live under
`login/`. The four initial targets are Douyin, Kuaishou, Xiaohongshu and
Weixin Channels. A protocol marked `pending` must not be treated as an API
implementation until its create and poll operations have both been observed.
