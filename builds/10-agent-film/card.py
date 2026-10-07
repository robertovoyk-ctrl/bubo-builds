# End card (1080x1920) and the opening title overlay (title.png, transparent). Committed, since Colab has no fonts.
from PIL import Image, ImageDraw, ImageFont
W, H = 1080, 1920
mono = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'; bold = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
G, R, D, M = (40, 255, 90), (255, 40, 110), (120, 130, 125), (225, 255, 238)
im = Image.new('RGB', (W, H), (2, 3, 3)); d = ImageDraw.Draw(im)
f1, f2, f3 = ImageFont.truetype(mono, 44), ImageFont.truetype(bold, 92), ImageFont.truetype(mono, 40)
y = 640
d.text((90, y), '$ claude -p "..."', font=f1, fill=G); y += 140
d.text((90, y), '3 keys found.', font=f2, fill=R); y += 110
d.text((90, y), '1 you already', font=f2, fill=R); y += 110
d.text((90, y), 'deleted.', font=f2, fill=R); y += 170
d.text((90, y), 'the prompt is in the post.', font=f3, fill=D)
im.save('card.png')
t = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
for i in range(420):                                   # soft dark band behind the title
    d.line([(0, i), (W, i)], fill=(0, 0, 0, int(215 * (1 - i / 420) ** 1.3)))
ft = ImageFont.truetype(bold, 86)
d.text((70, 90), 'Paste this into', font=ft, fill=M)
d.text((70, 195), 'your agent.', font=ft, fill=G)
t.save('title.png'); print('ok')
