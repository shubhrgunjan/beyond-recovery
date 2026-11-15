"""Verify automatic artifacts for a trial stopped immediately after creation."""
import asyncio
import json
import os
from pathlib import Path

import aiohttp


async def main():
    url=os.environ.get('BR_LIVE_URL','http://127.0.0.1:8082')
    async with aiohttp.ClientSession() as session:
        async def status():
            async with session.get(url+'/api/status') as response:
                response.raise_for_status()
                return await response.json()
        for _ in range(100):
            try:
                before=(await status()).get('run_id')
                break
            except aiohttp.ClientError:
                await asyncio.sleep(.2)
        else:
            raise AssertionError('Live service did not become ready')
        async with session.post(url+'/api/action',json={
            'action':'start','scenario':'open_floor','label':'Verification · immediate stop'}) as response:
            assert response.status==200
        async with session.post(url+'/api/action',json={'action':'stop'}) as response:
            assert response.status==200
        for _ in range(300):
            data=await status()
            if data['state']=='finished' and data['run_id']!=before:
                break
            assert data['state']!='error',data
            await asyncio.sleep(.05)
        assert data['state']=='finished',data
        for filename in ('video.mp4','figures.png','trace.npz','telemetry.jsonl','events.jsonl','manifest.json','summary.json'):
            async with session.get(f'{url}/runs/{data["run_id"]}/{filename}') as response:
                assert response.status==200,(filename,response.status)
                assert len(await response.read())>0
        report=dict(immediate_stop_run=data['run_id'],simulated_seconds=data['sim_time'],complete_artifacts=True)
        Path('artifacts/live-immediate-stop.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS:',json.dumps(report),flush=True)


asyncio.run(main())
