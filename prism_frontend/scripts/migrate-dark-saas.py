#!/usr/bin/env python3
"""Migrate hardcoded white/black utility classes to theme tokens (deep SaaS dark).

Mapping principles:
- text-white/NN        -> text-foreground/NN        (semantic equivalent)
- text-white           -> text-foreground
- text-black           -> text-background            (inverse-contrast contexts)
- bg-black/NN          -> bg-card/NN                 (panels/surfaces)
- bg-black             -> bg-card
- bg-white/NN          -> bg-foreground/NN           (inverse buttons/highlights)
- bg-white             -> bg-foreground
- hover:bg-white/NN    -> hover:bg-accent/NN*        (hover feedback)
- hover:bg-white       -> hover:bg-accent
- hover:bg-black/NN    -> hover:bg-card/NN
- border-white/NN      -> border-border/NN*          (scaled to theme border)
- border-white         -> border-border
- border-black         -> border-border
- ring-white/NN        -> ring-border/NN

Exceptions (kept as-is):
- dialog / alert-dialog full-screen overlay: `fixed inset-0 z-50 bg-black/60` -> keep black
- checkbox checked state handled separately to primary (post-pass)

*NN scaling: border-white/10 is a ~10% white hairline, visually ~ border-border/70.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"
DRY = "--apply" not in sys.argv

# (regex, replacement) — applied in order, most specific first
RULES = [
    # --- compound fixes first ---
    # primary button text: black-on-primary reads wrong; use primary-foreground
    (r"bg-primary text-black\b", "bg-primary text-primary-foreground"),
    (r"bg-primary/90 text-black\b", "bg-primary/90 text-primary-foreground"),
    # --- text ---
    (r"text-white/60\b", "text-muted-foreground"),
    (r"text-white/55\b", "text-muted-foreground"),
    (r"text-white/50\b", "text-muted-foreground"),
    (r"text-white/45\b", "text-foreground/45"),
    (r"text-white/40\b", "text-foreground/40"),
    (r"text-white/35\b", "text-foreground/35"),
    (r"text-white/30\b", "text-foreground/30"),
    (r"text-white/25\b", "text-foreground/25"),
    (r"text-white/20\b", "text-foreground/20"),
    (r"text-white/15\b", "text-foreground/15"),
    (r"text-white/10\b", "text-foreground/10"),
    (r"text-white/90\b", "text-foreground/90"),
    (r"text-white/80\b", "text-foreground/80"),
    (r"text-white/70\b", "text-foreground/70"),
    (r"text-white/65\b", "text-foreground/65"),
    (r"text-white/85\b", "text-foreground/85"),
    (r"text-white/75\b", "text-foreground/75"),
    (r"\btext-white\b", "text-foreground"),
    (r"\btext-black\b", "text-background"),
    # --- backgrounds ---
    (r"hover:bg-white/20\b", "hover:bg-accent/60"),
    (r"hover:bg-white/15\b", "hover:bg-accent/50"),
    (r"hover:bg-white/10\b", "hover:bg-accent/50"),
    (r"hover:bg-white/8\b", "hover:bg-accent/40"),
    (r"hover:bg-white/5\b", "hover:bg-accent/40"),
    (r"hover:bg-white/90\b", "hover:bg-foreground/90"),
    (r"hover:bg-white/80\b", "hover:bg-foreground/80"),
    (r"hover:bg-white\b", "hover:bg-accent"),
    (r"hover:bg-black/60\b", "hover:bg-card/60"),
    (r"hover:bg-black/40\b", "hover:bg-card/40"),
    (r"hover:bg-black/30\b", "hover:bg-card/30"),
    (r"hover:bg-black/20\b", "hover:bg-card/20"),
    (r"hover:bg-black\b", "hover:bg-card"),
    (r"bg-white/90\b", "bg-foreground/90"),
    (r"bg-white/80\b", "bg-foreground/80"),
    (r"bg-white/65\b", "bg-foreground/65"),
    (r"bg-white/60\b", "bg-foreground/60"),
    (r"bg-white/50\b", "bg-foreground/50"),
    (r"bg-white/30\b", "bg-foreground/30"),
    (r"bg-white/20\b", "bg-foreground/20"),
    (r"bg-white/15\b", "bg-foreground/15"),
    (r"bg-white/10\b", "bg-foreground/10"),
    (r"bg-white/8\b", "bg-foreground/8"),
    (r"bg-white/5\b", "bg-foreground/5"),
    (r"\bbg-white\b", "bg-foreground"),
    (r"bg-black/95\b", "bg-card"),
    (r"bg-black/90\b", "bg-card/90"),
    (r"bg-black/80\b", "bg-card/80"),
    (r"bg-black/70\b", "bg-card/70"),
    (r"bg-black/60\b", "bg-card/60"),
    (r"bg-black/55\b", "bg-card/55"),
    (r"bg-black/50\b", "bg-card/50"),
    (r"bg-black/40\b", "bg-card/40"),
    (r"bg-black/30\b", "bg-card/30"),
    (r"bg-black/22\b", "bg-card/22"),
    (r"bg-black/20\b", "bg-card/20"),
    (r"bg-black/15\b", "bg-card/15"),
    (r"bg-black/10\b", "bg-card/10"),
    (r"bg-black/5\b", "bg-card/5"),
    (r"bg-black/0\b", "bg-card/0"),
    (r"\bbg-black\b", "bg-card"),
    # --- borders ---
    (r"border-white/50\b", "border-border"),
    (r"border-white/30\b", "border-border"),
    (r"border-white/25\b", "border-border/80"),
    (r"border-white/20\b", "border-border/80"),
    (r"border-white/15\b", "border-border/70"),
    (r"border-white/10\b", "border-border/70"),
    (r"border-white/8\b", "border-border/50"),
    (r"border-white/5\b", "border-border/40"),
    (r"\bborder-white\b", "border-border"),
    (r"\bborder-black\b", "border-border"),
    # --- rings ---
    (r"ring-white/40\b", "ring-border/80"),
    (r"ring-white/30\b", "ring-border/70"),
    (r"ring-white/20\b", "ring-border/50"),
    (r"ring-white/10\b", "ring-border/40"),
    (r"\bring-white\b", "ring-border"),
]

# Files whose full-screen overlays must keep black (line contains 'fixed inset-0 z-50 bg-black/60')
OVERLAY_BLACK = ("bg-black/60",)

# Files whose full-screen overlays must keep black (line contains 'fixed inset-0 z-50 bg-black/60')
OVERLAY_PATTERN = re.compile(r"fixed\s+inset-0\s+z-50\s+bg-black/60")

def migrate_file(path: Path, stats: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if OVERLAY_PATTERN.search(line):
            # protect full-screen overlay: keep bg-black/60 (replace rest of line normally)
            line = re.sub(r"bg-black/60\b", "OVERLAY_BLACK_KEEP", line)
        for pattern, repl in RULES:
            line, n = re.subn(pattern, repl, line)
            stats["total"] += n
        line = line.replace("OVERLAY_BLACK_KEEP", "bg-black/60")
        lines[i] = line
    text = "".join(lines)
    if text != original:
        if DRY:
            stats["files"] += 1
            return True
        path.write_text(text, encoding="utf-8")
        stats["files"] += 1
        return True
    return False

def main():
    stats = {"files": 0, "total": 0}
    targets = list((ROOT / "app").rglob("*.tsx")) + list((ROOT / "components").rglob("*.tsx"))
    for path in sorted(targets):
        migrate_file(path, stats)
    print(f"{'DRY-RUN' if DRY else 'APPLIED'}: {stats['files']} files, {stats['total']} replacements")

if __name__ == "__main__":
    main()
