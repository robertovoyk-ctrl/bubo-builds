# End card: the scan result, drawn as a terminal. Writes card.png (1080x1920).
from PIL import Image, ImageDraw, ImageFont
W, H = 1080, 1920
im = Image.new('RGB', (W, H), (2, 3, 3)); d = ImageDraw.Draw(im)
mono = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'; bold = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
f1, f2, f3 = ImageFont.truetype(mono, 44), ImageFont.truetype(bold, 92), ImageFont.truetype(mono, 40)
G, R, D = (40, 255, 90), (255, 40, 110), (120, 130, 125)
y = 640
d.text((90, y), '$ keyspider shop-api', font=f1, fill=G); y += 140
d.text((90, y), '3 live', font=f2, fill=R); y += 130
d.text((90, y), '1 deleted,', font=f2, fill=R); y += 110
d.text((90, y), 'still in git', font=f2, fill=R); y += 110
d.text((90, y), 'history', font=f2, fill=R); y += 170
d.text((90, y), 'deleting a key does not', font=f3, fill=D); y += 56
d.text((90, y), 'remove it from git.', font=f3, fill=D)
im.save('card.png'); print('ok')
