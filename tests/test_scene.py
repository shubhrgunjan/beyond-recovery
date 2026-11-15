"""GPU integration check: task geometry and explicit termination semantics."""
import pytest


def test_corridor_geometry_and_uninterrupted_step():
    torch = pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('Requires the Thor GPU environment')
    import yaml
    from beyond_recovery.cli import ROOT
    from beyond_recovery.environment import make_env, set_command
    task = yaml.safe_load((ROOT / 'configs/t1_narrow.yaml').read_text())
    env = make_env(task, 13)
    try:
        env.reset(seed=13)
        assert not env.cfg.auto_reset
        model = env.sim.mj_model
        assert model.geom('route_wall_0').contype == 1
        assert model.geom('route_wall_1').conaffinity == 1
        initial = env.scene['robot'].data.root_link_pos_w.clone()
        set_command(env, [.3, 0, 0])
        action = torch.zeros((1, env.action_manager.total_action_dim), device=env.device)
        env.step(action)
        assert env.episode_length_buf[0].item() == 1
        assert env.scene['robot'].data.root_link_pos_w[0, 2] > .5
        assert torch.linalg.vector_norm(env.scene['robot'].data.root_link_pos_w - initial) < .1
    finally:
        env.close()
