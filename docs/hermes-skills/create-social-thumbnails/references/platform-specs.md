# Platform presets

Use these as export presets, not as a promise that every placement in every app renders identically. Platform UIs change, and feed/profile crops can differ. Preserve an editable master and verify the current upload preview before publishing.

| Preset | Canvas | Ratio | Status | Typical use |
|---|---:|---:|---|---|
| `xiaohongshu` | 1080 × 1440 | 3:4 | Common working preset | Xiaohongshu image-note cover |
| `wechat-channels` | 1080 × 1260 | 6:7 | Common working preset | WeChat Channels feed cover |
| `youtube` | 3840 × 2160 | 16:9 | Official recommendation | Standard YouTube video thumbnail |
| `youtube-shorts` | 2160 × 3840 | 9:16 | Official recommendation | Uploaded YouTube Shorts thumbnail |
| `douyin` | 1080 × 1920 | 9:16 | Common working preset | Douyin vertical cover |

YouTube's current help page recommends 3840 × 2160 for videos and 2160 × 3840 for Shorts, with 16:9 and 9:16 respectively. Source: [YouTube Help — Add custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en).

The other dimensions are practical production presets rather than guarantees of a fixed official upload specification. When a client, publishing tool, or current in-app prompt supplies a different requirement, follow that requirement and keep the ratio unless the platform says otherwise.

## Generic ratio-only presets

Use these when the user specifies a ratio instead of a platform, or requests a deliberate custom canvas for a platform.

| Ratio | Working canvas | Typical use |
|---:|---:|---|
| `1:1` | 1080 × 1080 | Square social cover |
| `4:3` | 1600 × 1200 | Landscape presentation or classic video cover |
| `3:4` | 1080 × 1440 | Portrait social cover |
| `4:5` | 1080 × 1350 | Portrait feed cover |
| `6:7` | 1080 × 1260 | WeChat Channels-style portrait cover |
| `16:9` | 1920 × 1080 | General landscape video cover |
| `9:16` | 1080 × 1920 | Full-height vertical video cover |

When both platform and ratio are supplied, follow the explicit ratio and treat the platform as context for safe areas and feed behavior. For YouTube, prefer the higher official platform preset unless the user explicitly asks for a smaller 16:9 export.

## Safe-area guidance

These margins are design guidance, not platform-enforced metadata:

- Keep essential text and faces at least 6% of canvas width from left and right edges.
- Keep essential content at least 6% of canvas height from top and bottom edges.
- For vertical covers, reserve extra breathing room near the bottom-right because action controls or captions may overlap in some feeds.
- For profile-grid-dependent work, inspect the square or center crop before final delivery.

## Export

- Prefer PNG for screenshot-heavy or text-heavy designs.
- Prefer high-quality JPG for photographic designs when file size matters.
- Use sRGB.
- Do not upscale a low-resolution portrait without warning the user.
- Keep an editable master if downstream variants will be needed.
