# Prism Agent Bootstrap Prompt

This document is for OpenClaw, Codex, Claude Code, and Prism's built-in
HermesAgent. Its purpose is to take a fresh Prism checkout to a state where
platform login and publishing can be safely continued.

## Current Prism CLI platforms

- bilibili
- douyin
- kuaishou
- xiaohongshu
- channels
- baijiahao
- tiktok
- youtube

Image-post publishing is currently available through the CLI for Douyin,
Kuaishou, and Xiaohongshu.

## Startup prompt

Give the following instruction to an agent:

> You are working in the Prism repository, a multi-platform social publishing
> project. Your first task is not to explore historical uploaders. Bring the
> project to a runnable and verifiable state, then report the exact validation
> result.
>
> 1. Treat the repository root as the working directory.
> 2. Prefer the project CLI: `prism`; never call the upstream `sau` command.
> 3. Read `docs/agent-bootstrap.md` and inspect `prism --help` before
>    choosing a platform command.
> 4. Use platform-specific commands and fields. Do not pass YouTube playlist or
>    visibility fields to another platform; do not invent fields when a command
>    does not expose one.
> 5. Start by validating `prism --help`, then
>    `prism douyin --help`, `prism kuaishou --help`,
>    `prism xiaohongshu --help`, and `prism bilibili --help`.
> 6. When a login produces a QR-code image, display the image to the user or
>    explicitly identify the local image to scan.
> 7. Never attempt Bilibili QR login in a non-interactive environment; explain
>    the required local terminal command instead.
> 8. Report commands run, passed validations, missing dependencies, the current
>    readiness for login/upload, and the recommended next action.
>
> For a real publication, validate the selected account first. Use
> `upload-note` only for Douyin, Kuaishou, or Xiaohongshu. Use `upload-video`
> for all listed platforms and follow its own `--help` contract.

For a non-login QR transport check on Douyin, Kuaishou, or Xiaohongshu, run
`prism <platform> login --account qr_probe --qr-only --headless`. It emits a
JSON line with `event: qrcode`, `image_path`, and an image data URL, then exits
without persisting a successful login state.

## HermesAgent

HermesAgent receives this same project-level skill catalogue directly in its
runtime prompt. It should prefer Prism backend APIs for matrix work and the
`prism` CLI for an explicit single-platform operation. The instruction is a
contract for deterministic uploaders; it is not permission to guess browser
actions or change adapter code during publication.
