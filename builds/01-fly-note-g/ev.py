import asyncio, sys, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--allow-file-access-from-files']); pg = await b.new_page(viewport={'width':1080,'height':1080})
        await pg.goto(f'file://{sys.path[0]}/anim.html?fps=60'); await pg.evaluate('window.init()'); await pg.evaluate('window.frame(948)')
        ev = await pg.evaluate('window.EV'); t = await pg.evaluate('[GRAB_T,DROP_T,TABLE_END,LAND_T]')
        json.dump({'ev':ev,'t':t}, open('events.json','w')); print(len(ev), t, [e for e in ev if e[0]!='i'][:30]); await b.close()
asyncio.run(main())
