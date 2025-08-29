#!/usr/bin/env python3
"""
add_spaces_around_english.py

Backup the target markdown file and insert ASCII spaces between Japanese and ASCII (English) sequences,
while preserving fenced code blocks, inline code, images, links, autolinks and HTML tags.

Usage:
  python3 scripts/add_spaces_around_english.py [path/to/file.md]

If no path is provided, defaults to articles/aca-otel-tracing.md
"""
import re
import sys
from pathlib import Path

def main():
    target = Path('articles/aca-otel-tracing.md')
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(2)

    text = target.read_text(encoding='utf-8')
    bak = target.with_suffix(target.suffix + '.bak')
    if not bak.exists():
        bak.write_text(text, encoding='utf-8')

    placeholders = []

    def stash(pattern, s, kind):
        def repl(m):
            i = len(placeholders)
            placeholders.append((kind, m.group(0)))
            return f"__PH_{kind}_{i}__"
        return re.sub(pattern, repl, s, flags=re.M|re.S)

    s = text
    # stash fenced code blocks (```...```)
    s = stash(r'```.*?```', s, 'CODE')
    # stash inline code `...`
    s = stash(r'`[^`\n]+`', s, 'INLCODE')
    # stash images ![alt](url)
    s = stash(r'!\[[^\]]*\]\([^\)]+\)', s, 'IMAGE')
    # stash links [text](url)
    s = stash(r'\[[^\]]+\]\([^\)]+\)', s, 'LINK')
    # stash autolinks <http...>
    s = stash(r'<https?://[^>]+>', s, 'AUTOLINK')
    # stash inline HTML tags
    s = stash(r'<[^>]+>', s, 'HTML')

    # Japanese and ASCII classes
    JP = r"[\u3000-\u303F\u3040-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]"
    EN = r"[A-Za-z0-9@%&=\+:#/\.\-_,\?]+"

    # insert space between JP and EN
    s, n1 = re.subn(rf'({JP})({EN})', r'\1 \2', s)
    # insert space between EN and JP
    s, n2 = re.subn(rf'({EN})({JP})', r'\1 \2', s)
    # repeat to catch chained cases
    for _ in range(2):
        s, r1 = re.subn(rf'({JP})({EN})', r'\1 \2', s)
        s, r2 = re.subn(rf'({EN})({JP})', r'\1 \2', s)
        n1 += r1; n2 += r2

    # restore placeholders
    for i, (kind, orig) in enumerate(placeholders):
        token = f"__PH_{kind}_{i}__"
        s = s.replace(token, orig)

    if s != text:
        target.write_text(s, encoding='utf-8')
        print(f"Updated {target} (backup: {bak}) — added spaces JP->EN: {n1}, EN->JP: {n2}")
    else:
        print("No changes necessary.")

if __name__ == '__main__':
    main()
