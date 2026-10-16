# Titles, descriptions, tags and cover copy

## Content facts

Start from the footage, subtitles, the user's notes and verifiable product material. The filming location is not automatically the topic; a city appearing in an ad doesn't make it a city-targeted campaign. No tests, rankings or performance numbers unless they are sourced. If the user specifies the main title verbatim, keep it; don't rewrite it into a city campaign or a new performance claim.

Internally compare three hooks (question, result, scenario/specific detail) and pick one; don't make the user fill in a form. Platform title, cover copy and body text each carry their own information; don't cram the full title onto the image.

## Fields and current Prism generation limits

| Platform | Title length | Tag limit | Field notes |
| --- | --- | --- | --- |
| Douyin | 20 | 4 | Video and image-post uploaders check separately; conservative generation limit |
| Xiaohongshu | 20 | 10 | Separate title and body; clear search keywords |
| Bilibili | 80 | 12 | `tags` is its own array; description and category filled separately |
| WeChat Channels | 30 | 4 | First sentence of the description carries the information; also produce `short_title` (current chain checks a 16-character limit) |
| Kuaishou | 30 | 3 | Map description and topics according to the uploader's fields |
| TikTok | 30 | 5 | Choose language by audience; don't default to bilingual |
| YouTube | 100 | 15 | Title, description and tags separate |

Source: Prism `ai_service/title_topic_generator.py` `PLATFORM_META`. Generation limits are not permanent official platform limits. When project source is available, check the generator, metadata adapter and the relevant uploader first; on conflict, use the value the current chain accepts and say so. In a standalone install without source, don't treat these as current platform policy.

## Writing

- Douyin: put the concrete hook first, short and natural; contrast must be grounded. Avoid empty "shocking/insane".
- WeChat Channels: complete, credible, easy to retell. For home and product content, write from the real-life need; don't force emotion.
- Bilibili: concrete subject, question or method, key content in the first half. No "hardcore test" without the content to back it.
- Xiaohongshu: subject, scenario, method and verifiable value; keywords that match real searches; don't fake personal experience.

Main cover copy is usually 4–10 Chinese characters or two short phrases; exact brand copy may be broken across lines as given. Character counts are a design starting point. Keep one main message; secondary copy is optional. The body adds scope, scenario and source; tags are relevant and de-duplicated, not filled up to the limit for its own sake.

Cross-platform difference comes from information structure and emphasis, not from unproven rules like "change 30% to avoid duplicate detection". There's no universal ban on emoji; follow brand tone, user request and the actual uploader.

## Product claims

Copy may only claim what the product logic sheet's "What it is for" section supports with a source. Don't add angles, recognition rates, specs, rankings or "world first" claims that the material doesn't confirm.

## Publish package

Per platform deliver `title`, `description`, `tags`, `cover_copy`, `cover_path`, plus `short_title` for WeChat Channels. Whether tags include `#` follows the current UI/MCP/CLI schema; don't hard-code one display format into every interface.

Cover-only requests may include a suggested title but don't publish. Copy-only requests don't consume image credits.
