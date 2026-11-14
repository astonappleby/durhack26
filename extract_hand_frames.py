"""Rebuild the bundled PNG/SVG poses from the Wikimedia GIF (requires Pillow)."""
from pathlib import Path
from PIL import Image

ASSETS = Path(__file__).resolve().parent / 'assets' / 'hands'


def extract_frames():
    with Image.open(ASSETS / 'source.gif') as animation:
        if animation.n_frames != 32:
            raise ValueError('Expected 32 frames in the source GIF')
        for number in range(32):
            animation.seek(number)  # Pillow composites partial GIF frames correctly.
            frame = animation.convert('RGBA')
            bits = ''.join(str((number >> finger) & 1) for finger in range(5))
            for view, fill in [('F', (255, 255, 255)), ('B', (105, 119, 139))]:
                pose = frame.copy()
                for y in range(pose.height):
                    for x in range(pose.width):
                        r, g, b, a = pose.getpixel((x, y))
                        if a and r > 200 and g > 200 and b > 200:
                            pose.putpixel((x, y), (*fill, a))
                stem = ASSETS / f'{view}_{bits}'
                pose.save(stem.with_suffix('.png'))
                # Lossless vectorization: merge identical pixels into horizontal runs.
                runs = []
                for y in range(pose.height):
                    x = 0
                    while x < pose.width:
                        color = pose.getpixel((x, y))
                        end = x + 1
                        while end < pose.width and pose.getpixel((end, y)) == color:
                            end += 1
                        if color[3]:
                            rgb = '#%02x%02x%02x' % color[:3]
                            runs.append(f'<rect x="{x}" y="{y}" width="{end-x}" height="1" fill="{rgb}"/>')
                        x = end
                stem.with_suffix('.svg').write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="31" '
                    'viewBox="0 0 24 31" shape-rendering="crispEdges">'
                    + ''.join(runs) + '</svg>', encoding='utf-8')
    print('Extracted 32 poses; saved 64 SVGs and 64 PNGs including dark backhand variants.')


if __name__ == '__main__':
    extract_frames()
