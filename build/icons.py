#!/usr/bin/python3
"""workflow/icons/ 의 PNG 아이콘을 생성한다.

외부 패키지도 Cocoa 도 쓰지 않는다. 시스템 파이썬에는 PyObjC 가 없고, 이미지
라이브러리를 끌어오면 이 프로젝트의 '의존성 0' 전제가 깨진다. zlib 만으로 PNG 를
직접 쓰고 도형은 스캔라인으로 칠한다.

안티에일리어싱은 SS 배로 크게 그린 뒤 평균내는 방식(수퍼샘플링)이다.

색은 국내 시장 관례를 따른다. 상승 빨강, 하락 파랑.
"""

from __future__ import annotations

import math
import os
import struct
import zlib

SIZE = 128       # 최종 한 변 픽셀. Alfred 목록에서 레티나로도 충분하다.
SS = 4           # 수퍼샘플링 배율

RED = (0xE0, 0x43, 0x3C)      # 상승·매수
BLUE = (0x2F, 0x6F, 0xE4)     # 하락·매도
GRAY = (0x8A, 0x8F, 0x98)     # 보합·정보
YELLOW = (0xF5, 0xB3, 0x01)   # 관심종목
ORANGE = (0xE8, 0x91, 0x2D)   # 경고
SLATE = (0x4B, 0x55, 0x63)    # 계좌


# --- PNG 쓰기 ---------------------------------------------------------------

def _chunk(tag, data):
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path, width, height, pixels):
    """RGBA 바이트열을 PNG 로 저장한다. pixels 는 width*height*4 바이트."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 필터 타입 0 (None)
        raw.extend(pixels[y * stride:(y + 1) * stride])

    blob = b"\x89PNG\r\n\x1a\n"
    blob += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    blob += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    blob += _chunk(b"IEND", b"")

    with open(path, "wb") as handle:
        handle.write(blob)


# --- 래스터라이즈 -----------------------------------------------------------

def _fill(mask, width, height, points):
    """다각형 내부를 mask 에 1 로 칠한다. 짝수-홀수 규칙 스캔라인."""
    edges = []
    count = len(points)
    for index in range(count):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % count]
        if y0 != y1:
            edges.append((x0, y0, x1, y1))

    for y in range(height):
        center = y + 0.5
        crossings = []
        for x0, y0, x1, y1 in edges:
            if (y0 <= center < y1) or (y1 <= center < y0):
                crossings.append(x0 + (center - y0) * (x1 - x0) / (y1 - y0))
        crossings.sort()

        for pair in range(0, len(crossings) - 1, 2):
            start = max(0, int(math.ceil(crossings[pair] - 0.5)))
            end = min(width - 1, int(math.floor(crossings[pair + 1] - 0.5)))
            for x in range(start, end + 1):
                mask[y * width + x] = 1


def render(shapes, path):
    """(점목록, 색) 목록을 겹쳐 그려 PNG 로 저장한다.

    점은 0..1 단위 좌표로 준다. 위가 y=0 이다.
    """
    big = SIZE * SS
    # 채널별 누적 버퍼. 나중에 SS*SS 로 평균낸다.
    layers = []
    for points, color in shapes:
        mask = bytearray(big * big)
        _fill(mask, big, big, [(x * big, y * big) for x, y in points])
        layers.append((mask, color))

    pixels = bytearray(SIZE * SIZE * 4)
    block = SS * SS
    for y in range(SIZE):
        for x in range(SIZE):
            # 나중에 그린 도형이 위로 오도록 뒤에서부터 훑어 처음 만난 것을 쓴다.
            for mask, color in reversed(layers):
                covered = 0
                for sy in range(SS):
                    row = (y * SS + sy) * big + x * SS
                    for sx in range(SS):
                        covered += mask[row + sx]
                if covered:
                    offset = (y * SIZE + x) * 4
                    pixels[offset] = color[0]
                    pixels[offset + 1] = color[1]
                    pixels[offset + 2] = color[2]
                    pixels[offset + 3] = covered * 255 // block
                    break

    write_png(path, SIZE, SIZE, pixels)


# --- 도형 -------------------------------------------------------------------

def triangle_up():
    return [(0.50, 0.16), (0.90, 0.82), (0.10, 0.82)]


def triangle_down():
    return [(0.50, 0.84), (0.10, 0.18), (0.90, 0.18)]


def bar(top, bottom, left=0.12, right=0.88):
    return [(left, top), (right, top), (right, bottom), (left, bottom)]


def circle(cx=0.5, cy=0.5, r=0.38, segments=72):
    return [
        (cx + r * math.cos(2 * math.pi * i / segments),
         cy + r * math.sin(2 * math.pi * i / segments))
        for i in range(segments)
    ]


def star(cx=0.5, cy=0.52, outer=0.42, inner=0.17):
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def rounded_rect(left, top, right, bottom, radius, segments=12):
    """모서리를 둥글린 사각형. 계좌(카드) 아이콘에 쓴다."""
    corners = [
        (right - radius, top + radius, -math.pi / 2, 0),
        (right - radius, bottom - radius, 0, math.pi / 2),
        (left + radius, bottom - radius, math.pi / 2, math.pi),
        (left + radius, top + radius, math.pi, 3 * math.pi / 2),
    ]
    points = []
    for cx, cy, start, end in corners:
        for step in range(segments + 1):
            angle = start + (end - start) * step / segments
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


ICONS = {
    # 등락
    "up": [(triangle_up(), RED)],
    "down": [(triangle_down(), BLUE)],
    "flat": [(bar(0.46, 0.54), GRAY)],

    # 관심종목
    "star": [(star(), YELLOW)],

    # 호가. 매도는 파랑이고 위쪽, 매수는 빨강이고 아래쪽에 놓아 호가창 배열과
    # 같은 방향으로 읽히게 한다.
    "ask": [(bar(0.30, 0.42), BLUE), (bar(0.50, 0.58, 0.24, 0.76), (0xC7, 0xD2, 0xE4))],
    "bid": [(bar(0.58, 0.70), RED), (bar(0.42, 0.50, 0.24, 0.76), (0xE9, 0xD2, 0xD0))],

    # 그 밖
    "info": [(circle(r=0.34), GRAY)],
    "warn": [(triangle_up(), ORANGE)],
    "account": [(rounded_rect(0.12, 0.26, 0.88, 0.74, 0.10), SLATE)],
}


def build():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(root, "workflow", "icons")
    os.makedirs(target, exist_ok=True)

    for name, shapes in sorted(ICONS.items()):
        render(shapes, os.path.join(target, name + ".png"))
    return target, len(ICONS)


if __name__ == "__main__":
    path, count = build()
    print("{0}개 생성: {1}".format(count, path))
