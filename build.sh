#!/bin/bash
# .alfredworkflow 번들을 만든다.
#
# .alfredworkflow 는 info.plist 가 최상위에 있는 폴더를 zip 으로 압축하고 확장자만
# 바꾼 것이다. 그래서 하는 일은 (1) info.plist 생성 (2) workflow/ 내용물을 zip
# 두 가지뿐이다. 압축할 때 workflow/ 디렉터리 자체가 아니라 그 "내용물"이 아카이브
# 루트에 와야 한다. 한 겹 더 들어가면 Alfred 가 info.plist 를 찾지 못한다.
set -euo pipefail

cd "$(dirname "$0")"

NAME="Toss Invest"
OUT="dist/${NAME}.alfredworkflow"

echo "==> 아이콘 생성"
/usr/bin/python3 build/icons.py

echo "==> info.plist 생성"
/usr/bin/python3 build/info_plist.py

echo "==> plist 검증"
plutil -lint workflow/info.plist

echo "==> 문법 검증"
/usr/bin/python3 -m compileall -q workflow

echo "==> 번들 생성"
rm -rf dist
mkdir -p dist
# __pycache__ 는 인터프리터 버전에 묶여 있어 배포본에 들어가면 안 된다.
find workflow -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
( cd workflow && zip -r -q -X "../${OUT}" . \
    -x '.DS_Store' '*/.DS_Store' '*.pyc' '__pycache__/*' '*/__pycache__/*' \
       '.omc/*' '*/.omc/*' )

echo "==> 완료: ${OUT}"
unzip -l "${OUT}"
