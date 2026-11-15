"""Exercise the real HTTP/WebSocket controls against a running Thor simulation."""
import asyncio
import json
import os
from pathlib import Path
import time

import aiohttp


async def main():
    base=os.environ.get('BR_LIVE_URL','http://127.0.0.1:8082')
    async with aiohttp.ClientSession() as session:
        async def status():
            async with session.get(base+'/api/status') as r:
                r.raise_for_status();return await r.json()
        async def action(kind,**kw):
            async with session.post(base+'/api/action',json=dict(action=kind,**kw)) as r:
                r.raise_for_status();return await r.json()
        async def until(predicate,timeout=15):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                data=await status()
                assert data['state']!='error',data
                if predicate(data):return data
                await asyncio.sleep(.06)
            raise AssertionError('Timed out waiting for state: '+str(await status()))
        await action('start',scenario='open_floor',label='Verification · live controls',
                     settings=dict(seed=11,speed=.4,force_scale=1,controller='reference'))
        first=await until(lambda s:s['state']=='running' and s['sim_time']>.3)
        await asyncio.sleep(.25)
        second=await status()
        assert second['sim_time']>first['sim_time']
        assert second['positions']!=first['positions']
        await action('pause');paused=await until(lambda s:s['state']=='paused')
        await asyncio.sleep(.25);assert (await status())['sim_time']==paused['sim_time']
        await action('step');stepped=await until(lambda s:s['sim_time']>paused['sim_time'])
        assert abs(stepped['sim_time']-paused['sim_time']-.02)<1e-8
        await action('resume');await until(lambda s:s['state']=='running')
        await action('manual',enabled=True);await until(lambda s:s['manual'])
        await action('drive',velocity=[.2,0,0]);await asyncio.sleep(.2)
        await action('manual',enabled=False)
        await action('push',strength=40,duration=.16,direction='+y')
        pushed=await until(lambda s:any(e['kind']=='push' for e in s['events']))
        async with session.ws_connect(base+'/ws') as ws:
            p1=await ws.receive_json();p2=await ws.receive_json()
            assert p2['seq']>=p1['seq'] and len(p1['positions'])>20
        await asyncio.sleep(.2);await action('stop')
        finished=await until(lambda s:s['state']=='finished')
        run=finished['run_id']
        for filename in ('video.mp4','figures.png','trace.npz','telemetry.jsonl','events.jsonl','manifest.json','summary.json','analysis.json','analysis.md'):
            async with session.get(f'{base}/runs/{run}/{filename}') as r:
                assert r.status==200,(filename,r.status)
                payload=await r.read();assert payload
        async with session.post(base+'/api/action',json={'action':'drive','velocity':[1,2]}) as r:
            assert r.status==400
        print('PASS: evolving live physics, freeze/pause, exact 20 ms step, manual drive, push, WebSocket, stop and every artifact.',flush=True)
        for scene in ['warehouse_aisle','warehouse_detour','office_round','doorway','slippery_floor','compound','endurance']:
            await action('select',scenario=scene)
            data=await until(lambda s:s['scenario']==scene and s['state']=='ready')
            assert data['sim_time']==0
            print('PASS: physical scene load:',scene,flush=True)
        # A full live failure trial exercises automatic termination, video and plot finalization.
        await action('start',scenario='compound',label='Verification · live compound disturbance',
                     settings=dict(seed=0,speed=.4,force_scale=1,controller='reference'))
        await until(lambda s:s['state']=='running')
        failure=await until(lambda s:s['state']=='finished',timeout=50)
        print('Compound live result:',failure['result'],failure['sim_time'],'s',flush=True)
        assert failure['result'] in ('recovery_failed','success','timeout')
        if failure['falls']:
            assert failure['sim_time']>failure['falls'][0]['start']+1
        await action('select',scenario='open_floor')
        await until(lambda s:s['scenario']=='open_floor' and s['state']=='ready')
        report={'controls_run':run,'compound_run':failure['run_id'],
                'compound_result':failure['result'],'compound_time':failure['sim_time'],
                'checks':'live physics; pause; step; manual; push; ws; recording; 8 physical scenes',
                'browser_visual_qa':'Unavailable: no connected browser automation surface'}
        path=Path('artifacts/live-validation.json');path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)

asyncio.run(main())
