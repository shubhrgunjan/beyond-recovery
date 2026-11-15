"""Thin browser replay of recorded MuJoCo states. No physics runs on the client."""
import json
from pathlib import Path
import time

import mjviser
import mujoco
import numpy as np
import viser


def run(args):
    folder = Path(args.run)
    model = mujoco.MjModel.from_binary_path(str(folder / 'scene.mjb'))
    trace = np.load(folder / 'trace.npz')
    poses, times = trace['qpos'], trace['time']
    data = mujoco.MjData(model)
    server = viser.ViserServer(host='127.0.0.1', port=args.port,
                               label='Beyond Recovery — recorded baseline')
    scene = mjviser.ViserMujocoScene(server, model, 1)
    server.gui.add_markdown('**Recorded G1 trial** — playback of saved simulation states.')
    summary = json.loads((folder / 'summary.json').read_text())
    server.gui.add_markdown(f"Task: **{folder.name}** · Result: **{summary['result']}**\n\n"
                             f"Subgoals: {summary['completed_subgoals']}/{summary['total_subgoals']}")
    playing = server.gui.add_checkbox('Play', initial_value=False)
    speed = server.gui.add_slider('Playback speed', min=.25, max=3, step=.25, initial_value=1)
    frame = server.gui.add_slider('Frame', min=0, max=len(poses)-1, step=1, initial_value=0)
    clock = server.gui.add_markdown('Time: 0 s')
    scene.create_scene_gui()
    scene.create_visualization_gui()
    previous = -1
    print(f'Replay ready at http://127.0.0.1:{args.port}', flush=True)
    try:
        while True:
            index = int(frame.value)
            if index != previous:
                data.qpos[:] = poses[index]
                mujoco.mj_forward(model, data)
                scene.update_from_mjdata(data)
                clock.content = f'Time: **{times[index]:.2f} s** · frame {index}/{len(poses)-1}'
                previous = index
            if playing.value:
                frame.value = (index + 1) % len(poses)
            dt = float(times[1] - times[0]) if len(times) > 1 else .02
            time.sleep(dt / float(speed.value))
    finally:
        server.stop()
