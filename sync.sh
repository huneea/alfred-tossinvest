#!/bin/bash
# 작업 중인 소스를 이미 설치된 워크플로우에 즉시 반영한다.
#
# build.sh 로 번들을 만들어 다시 임포트하는 것보다 빠르고, 무엇보다 설정을 잃지
# 않는다. 지켜야 할 것이 두 가지 있다.
#
#   prefs.plist  자격증명(Client ID/Secret)이 여기 있다. 절대 건드리지 않는다.
#   info.plist   사용자가 지정한 핫키가 여기 들어 있다. 덮어쓰기 전에 뽑아서
#                새로 만든 plist 에 다시 심는다.
set -euo pipefail

cd "$(dirname "$0")"

BUNDLE_ID="me.hhjung.tossinvest"
WORKFLOWS="$HOME/work/tools/alfred-preferences/Alfred.alfredpreferences/workflows"

echo "==> 설치본 찾기"
TARGET=""
for plist in "$WORKFLOWS"/*/info.plist; do
    if grep -qa "$BUNDLE_ID" "$plist" 2>/dev/null; then
        TARGET="$(dirname "$plist")"
        break
    fi
done

if [ -z "$TARGET" ]; then
    echo "설치된 워크플로우를 찾지 못했습니다 (bundleid: $BUNDLE_ID)." >&2
    echo "먼저 ./build.sh 로 번들을 만들어 한 번 설치하세요." >&2
    exit 1
fi
echo "    $TARGET"

echo "==> info.plist 생성"
/usr/bin/python3 build/info_plist.py >/dev/null

echo "==> 사용자 설정 보존"
/usr/bin/python3 build/preserve_hotkey.py "$TARGET/info.plist" workflow/info.plist | sed 's/^/    /'

echo "==> 검증"
plutil -lint workflow/info.plist >/dev/null
/usr/bin/python3 -m compileall -q workflow
echo "    plist·문법 OK"

echo "==> 동기화"
find workflow -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
# --delete 로 소스에서 지운 파일이 설치본에 남지 않게 한다. 제외한 파일은
# rsync 가 삭제 대상에서도 빼주므로 prefs.plist 는 안전하다.
rsync -a --delete \
    --exclude 'prefs.plist' \
    --exclude '.DS_Store' \
    --exclude '__pycache__' \
    --exclude '.omc' \
    --itemize-changes \
    workflow/ "$TARGET/" | sed 's/^/    /'

echo "==> Alfred 리로드"
osascript -e "tell application id \"com.runningwithcrayons.Alfred\" to reload workflow \"$BUNDLE_ID\"" \
    || echo "    리로드 실패 — Alfred 를 직접 재시작하세요"

echo "==> 완료"
