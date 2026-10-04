import asyncio, sys, base64, os
from playwright.async_api import async_playwright
mode = sys.argv[1]; fps = int(sys.argv[2]); out = sys.argv[3]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--allow-file-access-from-files'])
        pg = await b.new_page(viewport={'width':1080,'height':1080})
        pg.on('console', lambda m: print('JS', m.text))
        pg.on('pageerror', lambda e: print('ERR', e))
        await pg.goto(f'file://{sys.path[0]}/anim.html?fps={fps}')
        info = await pg.evaluate('window.init()'); print(info, await pg.evaluate('[GRAB_T,DROP_T,TABLE_END,LAND_T]'))
        os.makedirs(out, exist_ok=True)
        if mode == 'stills':
            ts = [float(x) for x in sys.argv[4].split(',')]; cur = 0
            for t in ts:
                n = round(t*fps) - cur; cur += n
                await pg.evaluate(f'window.frame({n})')
                d = await pg.evaluate("document.getElementById('c').toDataURL('image/png')")
                open(f'{out}/t{t:05.2f}.png','wb').write(base64.b64decode(d.split(',')[1]))
        else:
            N = int(float(sys.argv[4])*fps)
            for i in range(N):
                await pg.evaluate('window.frame(1)')
                d = await pg.evaluate("document.getElementById('c').toDataURL('image/png')")
                open(f'{out}/f{i:04d}.png','wb').write(base64.b64decode(d.split(',')[1]))
        await b.close()
asyncio.run(main())
