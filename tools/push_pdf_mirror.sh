#!/usr/bin/env bash
# Publish the PDF library to a public GitHub mirror.
#
# Vercel's Hobby plan caps a deployment at 100 MB and the library is 3.1 GB, so the
# PDFs are served from here and the site only ships HTML + thumbnails. Hardlinks keep
# the copy free: the mirror and the library share one copy of every file on disk.
set -euo pipefail

SRC="${1:-/home/fahad/Desktop/fahad-com/pdfs}"
REPO="${2:-/home/fahad/Desktop/fahad-com-pdfs}"
NAME="${3:-fahadkhanlinux-create/fahad-com-pdfs}"
BRANCH=main

mkdir -p "$REPO"
if [ ! -d "$REPO/pdfs" ] || [ "$(ls "$REPO/pdfs" | wc -l)" != "$(ls "$SRC" | wc -l)" ]; then
  rm -rf "$REPO/pdfs"
  cp -al "$SRC" "$REPO/pdfs"
fi

cd "$REPO"
if [ ! -d .git ]; then
  git init -q -b "$BRANCH"
  git config user.email "fahadkhanlinux-create@users.noreply.github.com"
  git config user.name "fahadkhanlinux-create"
  cat > README.md <<'EOF'
# fahad.com book library — PDF mirror

Every PDF here is a public-domain text from [Project Gutenberg](https://www.gutenberg.org/),
rendered for fahad.com. Free to read, download and redistribute.

- `pdfs/<id>.pdf` — one file per book, `id` matching the book id used on fahad.com
- Served through `https://cdn.jsdelivr.net/gh/fahadkhanlinux-create/fahad-com-pdfs@main/pdfs/<id>.pdf`
EOF
fi

git add -A
git commit -q -m "Mirror the fahad.com public-domain PDF library" || echo "nothing new to commit"
echo "local objects: $(git count-objects -vH | grep size-pack)"
git remote add origin "https://github.com/$NAME.git" 2>/dev/null || git remote set-url origin "https://github.com/$NAME.git"
time git push -u origin "$BRANCH"
echo "PUSH DONE $(date)"