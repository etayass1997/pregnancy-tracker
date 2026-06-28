"""Generate PWA PNG icons for בטן מלאה pregnancy tracker."""
import struct, zlib, os, math


def lerp(a, b, t):
    return max(0, min(255, int(a + (b - a) * t)))


def make_png(size):
    S = size

    # Background: warm rose top → deep rose bottom
    top = (255, 143, 177)   # #FF8FB1
    bot = (176, 10, 82)     # #B00A52

    # Outer belly heart (tip at top, lobes at bottom — the womb shape)
    # Heart vertical extent: top at hcy - 0.85*hs, lobe-bottom at hcy + 1.66*hs
    hcx, hcy = S * 0.50, S * 0.46
    hsx = S * 0.27   # horizontal scale
    hsy = S * 0.22   # vertical scale (compressed so lobes stay in frame)

    # Inner baby heart (lobes at top, tip at bottom — conventional heart)
    bhcx, bhcy = S * 0.50, S * 0.60
    bhs = S * 0.10

    rows = bytearray()
    for y in range(S):
        rows.append(0)
        t = y / (S - 1)
        bg = (lerp(top[0], bot[0], t), lerp(top[1], bot[1], t), lerp(top[2], bot[2], t))

        for x in range(S):
            # Belly heart: upside-down heart (tip at top in image coords)
            nx = (x - hcx) / hsx
            ny = (y - hcy) / hsy
            in_belly = (nx*nx + ((ny - 0.15) - abs(nx)**(2.0/3.0))**2) <= 1.0

            # Baby heart: conventional heart (lobes at top, tip at bottom in image coords)
            bnx = (x - bhcx) / bhs
            bny = (y - bhcy) / bhs
            in_baby = (bnx*bnx + (bny + abs(bnx)**(2.0/3.0))**2) <= 1.0

            if in_belly:
                if in_baby:
                    rows.extend([255, 100, 155])  # rose pink baby heart
                else:
                    rows.extend([255, 255, 255])  # white belly
            else:
                rows.extend(bg)

    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', S, S, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(bytes(rows), 6)) +
            chunk(b'IEND', b''))


if __name__ == '__main__':
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    os.makedirs(static_dir, exist_ok=True)
    for size in [192, 512]:
        path = os.path.join(static_dir, f'icon-{size}.png')
        with open(path, 'wb') as f:
            f.write(make_png(size))
        print(f'Created {path}')
