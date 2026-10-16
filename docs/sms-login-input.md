# SMS login input maintenance

`PhoneLoginAdapter._code_target()` is shared by stage detection and submission.
It searches every frame, accepts one visible enabled input, and rejects ambiguous
forms. A visible code field exposes Prism's code box even if a countdown was not
recognized or the user requested SMS in the remote view. This does not claim SMS
delivery or login success. Explicit SMS rejection still blocks submission.
Only the normal cookie/profile polling path can confirm login.

## Selector evidence

No generated site classes or positional input selectors are used.

| Platform | Evidence and selectors | Remaining uncertainty |
| --- | --- | --- |
| Douyin | Existing `app_new/platforms/douyin_sms.py` and `tests/test_douyin_sms_browser.py`: frame inspection, a visible placeholder containing `验证码`, and an ancestor containing the form's controls. `tests/test_phone_login_flow.py` covers `登录`. Identity QR/account selection keep their existing priority. | Real creator/MCN login regression still needs user verification. |
| Xiaohongshu | Public creator login route loads [7334.d7395270.js](https://fe-static.xhscdn.com/formula-static/ugc/public/resource/js/async/7334.d7395270.js), inspected 2026-10-17. Its SMS form declares placeholder `手机号`, placeholder `验证码`, send labels `发送验证码` / `重新发送`, and countdown `${seconds}s`. The code matches the semantic placeholder and now recognizes this countdown. Login button matching retains the existing fixture's `登录` contract. | Authenticated/challenge variants and actual submission are not verified. |
| Kuaishou | Existing `phone_login.py` / `tests/test_phone_login_flow.py`: placeholder containing `验证码`, `登录`, and the existing `手机号码验证` heading with nearest input-containing ancestor and `确定` control for secondary verification. Existing `requestMobileCode` response handling remains authoritative for rejection/success. | These are repository contracts, not a fresh live login DOM capture. Secondary verification and slider-to-SMS handoff need real testing. |
| Bilibili | Existing `tests/test_phone_login_flow.py` explicitly exercises Bilibili with placeholder `请输入验证码` and button `登录`. The existing SMS tab labels are selected before waiting for the phone field. | Public passport fetch returned a security page; current live SMS form and challenge variants are unverified. |

`autocomplete="one-time-code"` is an additional semantic fallback already used
by `platforms/publish_verification.py`; it is not asserted to exist on every site.
Hidden duplicates are ignored; multiple visible fields fail closed.
The submit control is scoped to the code field's nearest ancestor containing the
submit label, following the existing Douyin form-scoping approach. The smaller
code-field wrapper can contain a send button; that wrapper is not the login form.

## Remote input contract

`POST /api/v1/auth/qrcode/pointer/{session_id}` retains pointer payloads and adds:

```json
{"action":"type","text":"user-provided text"}
```

```json
{"action":"key","key":"Shift+Tab"}
```

Both travel through the existing API proxy, worker interaction lock, and session
expiry checks. Text uses `keyboard.insert_text`; keys use `keyboard.press`.
The frontend shares the ordered pointer queue, supports direct image keyboard
input/paste, and provides a separate text area for IME/mobile text input. `focus`
in the frame response contains geometry only; input values are never returned.

## Manual acceptance (user account required)

For every platform, start an SMS session in Prism, request the code, complete any
human challenge, enter the user-received code in Prism's code box, and confirm
the account reaches logged in. Check wrong-code retry and resend cooldown too.

- Xiaohongshu: verify the pure `60s` countdown, code box visibility and submission.
- Kuaishou: verify slider rejection does not claim SMS delivery; finish the slider,
  request again, submit via Prism, and repeat for `手机号码验证` if presented.
- Bilibili: verify switching from password to SMS login exposes the phone field,
  then request and submit via Prism through any security challenge.
- Douyin: repeat creator and MCN flows, including associated account selection
  and original-device identity verification when presented.

For each, also click the platform input in the remote image; test direct typing,
paste, Backspace, Enter and Tab. Test Chinese IME in the helper text area. Verify
the blue focus marker and scrolling in normal/zoom/pan modes, including iframe
inputs. Keep recordings/logs local and redact personal data before sharing.
