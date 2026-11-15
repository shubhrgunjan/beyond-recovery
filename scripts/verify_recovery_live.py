"""Verify real-time trip, learned physical get-up and subsequent task advancement."""
import argparse,asyncio,json,time
from pathlib import Path
import aiohttp

parser=argparse.ArgumentParser();parser.add_argument('--tuned',action='store_true');args=parser.parse_args()

async def main():
    url='http://127.0.0.1:8082'
    async with aiohttp.ClientSession() as session:
        async with session.post(url+'/api/action',json=dict(action='start',scenario='trip_box_open',
            label='Verification · live trip, get-up and task resumption',
            settings=dict(controller='amp',seed=0,speed=.4,force_scale=1,amp_yaw_gain=4 if args.tuned else 1,arrival_mode='centered' if args.tuned else 'legacy'))) as response:
            assert response.status==200
        deadline=time.monotonic()+50
        recovered=resumed=None;last=None
        while time.monotonic()<deadline:
            async with session.get(url+'/api/status') as response:data=await response.json()
            if data['recovery_state']!=last:
                print(data['sim_time'],data['recovery_state'],flush=True);last=data['recovery_state']
            assert data['state']!='error',data
            for fall in data['falls']:
                if fall.get('recovered_at') is not None:recovered=fall
                if fall.get('task_resumed_at') is not None:resumed=fall
            if resumed:break
            await asyncio.sleep(.08)
        assert recovered and resumed,data
        async with session.post(url+'/api/action',json={'action':'stop'}) as r:assert r.status==200
        for _ in range(100):
            async with session.get(url+'/api/status') as response:data=await response.json()
            if data['state']=='finished':break
            await asyncio.sleep(.1)
        assert data['state']=='finished'
        report=dict(run_id=data['run_id'],fall=resumed,task_subgoals=data['phase'],no_state_reset=True)
        Path('artifacts/live-recovery-tuned-validation.json' if args.tuned else 'artifacts/live-recovery-validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS:',json.dumps(report),flush=True)

asyncio.run(main())
