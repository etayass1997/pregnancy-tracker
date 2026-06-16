"""Generate PWA PNG icons using only Python stdlib — no Pillow needed."""
import struct
import zlib
import os
import math


def make_png(size, bg_r, bg_g, bg_b, fg_r, fg_g, fg_b):
    """Create a PNG with a pink rounded-rect background and a white heart."""
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    # Pre-compute: rounded rectangle inside the square
    corner_radius = size // 5
    pad = size // 16
    rows = bytearray()

    for y in range(size):
        rows.append(0)  # filter None
        for x in range(size):
            # Rounded rectangle test
            ax = abs(x - size / 2) - (size / 2 - pad - corner_radius)
            ay = abs(y - size / 2) - (size / 2 - pad - corner_radius)
            dx = max(ax, 0)
            dy = max(ay, 0)
            in_rect = (dx * dx + dy * dy) <= corner_radius * corner_radius

            if in_rect:
                # Heart shape in the center third
                nx = (x - size / 2) / (size / 4)
                ny = (y - size / 2) / (size / 4)
                ny -= 0.15  # shift slightly upward
                heart = (nx * nx + (ny - abs(nx) ** (2 / 3)) ** 2) <= 1.0
                if heart:
                    rows.extend([255, 255, 255])
                else:
                    rows.extend([fg_r, fg_g, fg_b])
            else:
                rows.extend([bg_r, bg_g, bg_b])

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(bytes(rows), 6))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


if __name__ == '__main__':
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.makedirs(static_dir, exist_ok=True)

    # White background, pink (#F48FB1) rounded rect, white heart
    bg = (255, 255, 255)
    fg = (244, 143, 177)   # #F48FB1

    for size in [192, 512]:
        path = os.path.join(static_dir, f'icon-{size}.png')
        data = make_png(size, *bg, *fg)
        with open(path, 'wb') as f:
            f.write(data)
        print(f'Created {path} ({len(data)} bytes)')
