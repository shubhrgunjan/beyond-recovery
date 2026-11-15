"""Render selected saved physics states; never reruns or alters the experiment."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
import argparse,json
from pathlib import Path
import numpy as np
import mujoco,imageio.v2 as imageio
from PIL import Image,ImageDraw,ImageFont
from beyond_recovery.reference import build_robot
from beyond_recovery.recovery import AMPController
ROOT=Path(__file__).resolve().parents[1]

def render(row,name):
    path=Path(row['path']);manifest=json.loads((path/'manifest.json').read_text())
    model,data,*_=build_robot(manifest['task'],manifest['settings']['seed']);AMPController(model,data)
    trace=np.load(path/'trace.npz');times=trace['time'];poses=trace['qpos']
    camera=mujoco.MjvCamera();camera.distance=4.7;camera.azimuth=115;camera.elevation=-40
    visual=mujoco.MjvOption();visual.geomgroup[3:]=0
    model.vis.headlight.ambient[:]=.4;model.vis.headlight.diffuse[:]=.8
    for i,fixture in enumerate(manifest['task']['fixtures']):
        if fixture.get('label')=='Recovery-space barrier':model.geom_rgba[model.geom(f'fixture_{i}').id,3]=.25
    output=ROOT/'reports/clips';output.mkdir(exist_ok=True)
    renderer=mujoco.Renderer(model,height=540,width=960)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    with imageio.get_writer(output/f'{name}.mp4',fps=25,codec='libx264',quality=7,macro_block_size=2) as writer:
        for time in np.arange(0,times[-1]+.0001,.04):
            i=min(np.searchsorted(times,time),len(times)-1)
            data.qpos[:]=poses[i];mujoco.mj_forward(model,data)
            camera.lookat[:]=[data.qpos[0]+.4,data.qpos[1],.65]
            renderer.update_scene(data,camera=camera,scene_option=visual)
            frame=Image.fromarray(renderer.render());draw=ImageDraw.Draw(frame)
            draw.rectangle((0,0,960,88),fill='#17231f')
            draw.text((16,8),f'SAVED PHYSICS TRACE | {name} | t={time:.2f}s',font=font,fill='white')
            draw.text((16,34),f'Seed {row["seed"]} | result: {row["result"]} | fixed AMP controller',font=font,fill='#aee0c0')
            draw.text((16,60),'Support barriers shown translucent for visibility; physics unchanged',font=font,fill='#aab9b2')
            writer.append_data(np.asarray(frame))
    renderer.close()
    (output/f'{name}.json').write_text(json.dumps(dict(source_run=str(path),source_manifest=manifest,selection='Illustrative pair; aggregate results take precedence'),indent=2))
    print('RENDERED',name,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--support',action='store_true');args=parser.parse_args()
    if args.support:
        root=sorted((ROOT/'artifacts/research').glob('impact-*'))[-1]
        for row,name in zip(json.loads((root/'illustrative-support-pair.json').read_text()),('support-open','support-narrow')):render(row,name)
    else:
        root=sorted((ROOT/'artifacts/research').glob('matched-*'))[-1]
        rows=json.loads((root/'results.json').read_text())
        for seed in (0,17):
            for width in (None,.9):
                row=next(r for r in rows if r['seed']==seed and r['height']==.13 and r['width']==width)
                render(row,f'trip-seed{seed}-'+('open' if width is None else 'narrow'))
