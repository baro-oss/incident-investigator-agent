#!/usr/bin/env bash
#
# Đẩy demo source lên các repo GitLab rỗng của bạn.
#
# payment-gateway: 2 commit + 2 tag  (kịch bản "demo")
#   - v2.3.0 (GOOD): MAX_POOL_SIZE=50, có retry/except guard
#   - v2.4.0 (BAD) : MAX_POOL_SIZE=5, xoá retry guard  ← root cause agent sẽ tìm ra
# auth-service: 2 commit + 2 tag  (kịch bản "demo2")
#   - v1.1.0 (GOOD): jwt.decode(..., leeway=30) + try/except AuthenticationError
#   - v1.2.0 (BAD) : bỏ leeway + bỏ try/except + bump PyJWT 2.7→2.8  ← root cause demo2
# các service khác: 1 commit (stub) để read_file/service_repos chạy được.
#
# Cấu hình qua env:
#   GITLAB_NAMESPACE   (bắt buộc)  vd: baopx  hoặc my-group/sub
#   GITLAB_PUSH_TOKEN  (bắt buộc)  PAT scope write_repository  (fallback: GITLAB_TOKEN)
#   GITLAB_BASE        (tùy chọn)  mặc định https://gitlab.com
#   PUSH_FORCE=1       (tùy chọn)  thêm --force khi đẩy lại
#   ENTRIES="..."      (tùy chọn)  ghi đè map "<src-dir>:<repo>:<versioned 0|1>"
#
# Cách dùng:
#   GITLAB_NAMESPACE=baopx-microservices GITLAB_PUSH_TOKEN=glpat-xxxx bash demo/setup_gitlab_repos.sh
#
set -euo pipefail

SRC="$(cd "$(dirname "$0")/gitlab-src" && pwd)"
GITLAB_BASE="${GITLAB_BASE:-https://gitlab.com}"
TOKEN="${GITLAB_PUSH_TOKEN:-${GITLAB_TOKEN:-}}"
NS="${GITLAB_NAMESPACE:-}"
HOST="${GITLAB_BASE#https://}"; HOST="${HOST#http://}"; HOST="${HOST%/}"
FORCE=""; [ "${PUSH_FORCE:-0}" = "1" ] && FORCE="--force"
# map "<src-dir trong demo/gitlab-src>:<repo trên GitLab>:<versioned 0|1>"
ENTRIES="${ENTRIES:-payment-gateway:payment-gateway:1 api-gateway:api-gateway:0 auth-service:auth-service:1 order-service:order-service:0}"
DATE_PG_V230="2026-06-16T08:10:00"
DATE_PG_V240="2026-06-16T09:02:00"
DATE_AUTH_V110="2026-06-17T13:10:00"
DATE_AUTH_V120="2026-06-17T14:03:00"

if [ -z "$NS" ] || [ -z "$TOKEN" ]; then
  echo "❌ Cần GITLAB_NAMESPACE và GITLAB_PUSH_TOKEN (hoặc GITLAB_TOKEN có quyền write_repository)." >&2
  echo "   vd: GITLAB_NAMESPACE=baopx GITLAB_PUSH_TOKEN=glpat-xxx bash demo/setup_gitlab_repos.sh" >&2
  exit 1
fi

remote_url() { echo "https://oauth2:${TOKEN}@${HOST}/${NS}/$1.git"; }

commit_at() {  # commit_at <ISO_DATE> <message>
  GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1" \
    git -c user.name="Demo Bot" -c user.email="demo@example.com" \
    commit -q -m "$2"
}

push_repo() {  # push_repo <src_dir> <repo_name> <with_versions:0|1>
  local srcdir="$1" name="$2" versioned="$3"
  local build; build="$(mktemp -d)"
  echo "── $srcdir → $name ─────────────────────────────────────"
  cp -R "$SRC/$srcdir/." "$build/"
  ( cd "$build"
    git init -q -b main
    git add -A
    if [ "$versioned" = "1" ]; then
      case "$srcdir" in
        payment-gateway)
          commit_at "$DATE_PG_V230" "feat: payment-gateway v2.3.0 — pool + retry guard"
          git tag v2.3.0
          cp "$SRC/_v2.4.0/pool.py" "src/db/pool.py"
          git add -A
          commit_at "$DATE_PG_V240" "perf: tune connection pool sizing for cost optimization"
          git tag v2.4.0
          ;;
        auth-service)
          commit_at "$DATE_AUTH_V110" "feat: auth-service v1.1.0 — JWT verify with clock-skew leeway"
          git tag v1.1.0
          cp "$SRC/_auth_v1.2.0/validator.py" "src/auth/validator.py"
          cp "$SRC/_auth_v1.2.0/requirements.txt" "requirements.txt"
          git add -A
          commit_at "$DATE_AUTH_V120" "chore: upgrade PyJWT to 2.8.x and simplify token verification"
          git tag v1.2.0
          ;;
        *)
          commit_at "$DATE_PG_V230" "chore: initial commit"
          ;;
      esac
    else
      commit_at "$DATE_PG_V230" "chore: initial commit"
    fi
    git remote add origin "$(remote_url "$name")"
    git push $FORCE -u origin main >/dev/null 2>&1 || { echo "  ⚠️  push main lỗi (repo tồn tại + có commit? thử PUSH_FORCE=1)"; }
    git push $FORCE origin --tags >/dev/null 2>&1 || true
    echo "  ✅ đẩy xong → ${HOST}/${NS}/${name}"
  )
  rm -rf "$build"
}

for entry in $ENTRIES; do
  IFS=: read -r srcdir repo ver <<< "$entry"
  push_repo "$srcdir" "$repo" "$ver"
done

echo ""
echo "Hoàn tất. Kiểm tra:"
echo "  • tag v2.3.0 + v2.4.0 trên repo ${NS}/payment-gateway  (kịch bản demo)"
echo "  • tag v1.1.0 + v1.2.0 trên repo ${NS}/auth-service      (kịch bản demo2)"
echo "Tiếp theo: python3 scripts/setup_demo.py để map service_repos + MCP + Telegram."
