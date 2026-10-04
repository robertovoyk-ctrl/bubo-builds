import asyncio, sys, json, base64, os
from playwright.async_api import async_playwright
mode, logf, out = sys.argv[1], sys.argv[2], sys.argv[3]; FPS = 60
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width':1080,'height':1920})
        pg.on('pageerror', lambda e: print('ERR', e)); pg.on('console', lambda m: print('JS', m.text))
        await pg.goto(f'file://{sys.path[0]}/arena.html')
        info = await pg.evaluate('d=>window.setup(d)', json.load(open(logf)))
        json.dump(info, open('timeline.json','w')); print('total', round(info['total'],2))
        os.makedirs(out, exist_ok=True)
        if mode=='stills':
            ts=[float(x) for x in sys.argv[4].split(',')]
            if sys.argv[4]=='auto': pass
        else: ts=[i/FPS for i in range(int(info['total']*FPS))]
        for i, t in enumerate(ts):
            await pg.evaluate(f'window.frame({t})')
            d = await pg.evaluate("document.getElementById('c').toDataURL('image/png')")
            open(f'{out}/{("t%06.2f" % t) if mode=="stills" else ("f%05d" % i)}.png','wb').write(base64.b64decode(d.split(',')[1]))
        await b.close()
asyncio.run(main())
