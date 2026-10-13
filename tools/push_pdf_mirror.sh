#!/usr/bin/env bash
# Publish the PDF library to a public GitHub mirror, in resumable chunks.
#
# Why chunked: the library is ~3.4 GB and outbound bandwidth here is a few hundred
# KB/s, so a single `git push` of the whole tree runs for hours and then dies on a
# timeout -- which is how the mirror ended up empty while the site pointed 6589
# books at it. Each chunk is committed and pushed on its own, so a push that dies
# costs one chunk, not the whole run: rerun the script and it picks up where it
# stopped.
#
# Vercel's Hobby plan caps a deployment at 100 MB and GitHub warns above 1 GB, but
# per-file limits are not a problem here (the largest PDF is 8 MB, well under
# GitHub's 100 MB hard block). Hardlinks keep the mirror free on disk.
set -euo pipefail

SRC="${1:-/home/fahad/Desktop/fahad-com/pdfs}"
REPO="${2:-/home/fahad/Desktop/fahad-com-pdfs}"
NAME="${3:-fahadkhanlinux-create/fahad-com-pdfs}"
BRANCH=main
CHUNK="${CHUNK:-250}"
LOG="${LOG:-$REPO/push.log}"

# A slow link is the failure mode here: git's defaults let a transfer stall for
# minutes before giving up, and then retries the whole pack. These turn "stalled"
# into "abort this chunk, keep the last one that landed".
git_opts=(
  -c http.postBuffer=524288000
  -c http.lowSpeedLimit=1000
  -c http.lowSpeedTime=60
  -c core.compression=1
  -c pack.threads=1
  -c pack.windowMemory=64m
)

# This box resolves github.com to a NAT64 IPv6 address that drops mid-transfer --
# the mirror push died on "Could not resolve host" more than once. Pinning the
# name to a v4 address skips that route entirely; fall back to normal resolution
# if GitHub moves the address and the pin starts failing.
GITHUB_IP="${GITHUB_IP:-140.82.121.4}"
if curl -sf -o /dev/null -m 15 --resolve "github.com:443:$GITHUB_IP" https://github.com/; then
  git_opts+=(-c "http.curloptResolve=github.com:443:$GITHUB_IP")
  echo "==> pinning github.com to $GITHUB_IP (IPv6 route is unreliable here)"
else
  echo "==> $GITHUB_IP not serving github.com, using DNS as-is"
fi

mkdir -p "$REPO"
src_count=$(ls "$SRC" | wc -l)
if [ ! -d "$REPO/pdfs" ] || [ "$(ls "$REPO/pdfs" | wc -l)" != "$src_count" ]; then
  rm -rf "$REPO/pdfs"
  cp -al "$SRC" "$REPO/pdfs"
fi

cd "$REPO"
cat > README.md <<'EOF'
# fahad.com book library — PDF mirror

Every PDF here is a public-domain text from [Project Gutenberg](https://www.gutenberg.org/),
rendered for fahad.com. Free to read, download and redistribute.

- `pdfs/<id>.pdf` — one file per book, `id` matching the book id used on fahad.com
- Served through `https://cdn.jsdelivr.net/gh/fahadkhanlinux-create/fahad-com-pdfs@main/pdfs/<id>.pdf`
EOF

# Start from an empty history every run. A previous run left one local commit holding
# all 6969 PDFs, and git sends a whole snapshot per push, so that single commit made
# the first "chunked" push a 3.4 GB upload that stalled before it finished. With an
# empty history each chunk is a genuine increment and the push that carries it is
# proportional to the chunk.
if [ "${RESET_HISTORY:-1}" = "1" ]; then
  rm -rf .git
fi

git init -q -b "$BRANCH"
git config user.email "fahadkhanlinux-create@users.noreply.github.com"
git config user.name "fahadkhanlinux-create"
git add README.md
git commit -q -m "Add mirror README"

git remote add origin "https://github.com/$NAME.git" 2>/dev/null || git remote set-url origin "https://github.com/$NAME.git"

push_chunk() {
  # The mirror may hold a root commit from an earlier run that shares no history
  # with this clone (that is how the repo ended up empty while the tree here was
  # fully committed). Rewriting onto our own history is the point of a mirror, so
  # the first push is forced and the rest are fast-forwards.
  local force=""
  if [ -z "$force_done" ]; then force="--force"; fi
  # Retries a chunk rather than the run: a chunk that dies is re-added from scratch
  # next time round, and every chunk before it is already on the remote.
  local attempt=1
  while [ "$attempt" -le 5 ]; do
    if git "${git_opts[@]}" push -q $force origin "HEAD:$BRANCH" 2>>"$LOG"; then
      force_done=1
      return 0
    fi
    echo "  chunk push failed (attempt $attempt/5), retrying in 30s" | tee -a "$LOG"
    attempt=$((attempt + 1))
    sleep 30
  done
  return 1
}

total=$(ls pdfs | wc -l)
# set once the remote is known to carry our history, so only the first push forces
force_done=""
echo "==> $total PDFs to mirror in chunks of $CHUNK" | tee -a "$LOG"
done_n=0
chunk=0
batch=()
flush() {
  [ "${#batch[@]}" -eq 0 ] && return 0
  chunk=$((chunk + 1))
  printf '==> chunk %d (%d files, %d/%d done)\n' "$chunk" "${#batch[@]}" "$done_n" "$total"
  printf '%s\n' "${batch[@]}" | sed 's|^|pdfs/|' | tr '\n' '\0' | xargs -0 git add --
  # Push whether or not this chunk produced a commit. The tree is often already
  # committed locally from an earlier run that never reached the remote, and
  # skipping the push on an empty diff would leave the mirror empty forever.
  if ! git diff --cached --quiet; then
    git commit -q -m "Mirror PDFs: $(printf '%s ' "${batch[@]:0:3}")... (+${#batch[@]} files)"
  fi
  push_chunk
  done_n=$((done_n + ${#batch[@]}))
  batch=()
}

for f in $(ls pdfs); do
  batch+=("$f")
  if [ "${#batch[@]}" -ge "$CHUNK" ]; then flush; fi
done
flush

remaining=$(git ls-tree -r --name-only "origin/$BRANCH" 2>/dev/null | grep -c '^pdfs/' || true)
echo "PUSH DONE $(date) -- $remaining/$total pdfs on $BRANCH" | tee -a "$LOG"