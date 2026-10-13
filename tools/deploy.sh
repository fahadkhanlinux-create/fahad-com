#!/usr/bin/env bash
# Stage and publish fahad-com.
#
# Two Vercel Hobby limits shape this:
#   * 100 MB per deployment - stage_deploy.py keeps the site (HTML, JSON, thumbnails)
#     inside that and spends what is left on the most useful PDFs
#   * 5000 file uploads per deployment on the free tier - the library alone is 6839
#     thumbnails, so the upload must go as a single archive: vercel --archive=tgz
#
# The staged directory keeps its own .vercel link, and that link rots: a stale one
# points the deployment at a different project, which looks like a successful
# publish while the live site never changes. The repo's link is the truth.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"

python3 tools/stage_deploy.py
cd "${DEPLOY_DIR:-/tmp/opencode/fahad-com-deploy}"
mkdir -p .vercel
cp "$BASE/.vercel/project.json" .vercel/project.json
vercel --prod --yes --archive=tgz