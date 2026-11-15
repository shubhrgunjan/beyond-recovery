import numpy as np
import pytest

from beyond_recovery.live import support_margin, validate_command
from beyond_recovery.scenarios import get_scenario, scenarios


def test_support_margin_distinguishes_inside_and_outside_contact_polygon():
    feet = [[-.1,-.1,0],[.1,-.1,0],[.1,.1,0],[-.1,.1,0]]
    assert support_margin(feet, np.array([0.,0.])) == pytest.approx(.1)
    assert support_margin(feet, np.array([.2,0.])) == pytest.approx(-.1)
    assert support_margin(feet[:2],np.zeros(2)) is None


def test_live_controls_reject_nonfinite_and_unknown_inputs():
    for command in [dict(action='drive',velocity=[0,float('nan'),0]),
                    dict(action='push',direction='north'),
                    dict(action='start',scenario='missing'),
                    dict(action='start',settings={'speed':float('inf')})]:
        with pytest.raises(ValueError): validate_command(command)


def test_scenes_have_tasks_and_physical_friction_patch():
    assert len(scenarios()) >= 8
    assert all(s['question'] and s['waypoints'] for s in scenarios())
    patch = get_scenario('slippery_floor')['fixtures'][0]
    assert patch['friction'][0] == .08 and patch['priority'] > 0
    assert patch['center'][2]+patch['half_size'][2] == pytest.approx(.01)
    # Editing a trial never changes the catalogue or another trial's event budget.
    a=get_scenario('compound');a['pushes'][0]['force'][1]=0
    assert get_scenario('compound')['pushes'][0]['force'][1]==160


def test_doorway_route_does_not_cross_the_solid_wall():
    task=get_scenario('doorway')
    points=[[0,0],*task['waypoints']]
    # Every traversal of the x=3 wall must go through the central 1.2 m opening.
    for a,b in zip(points,points[1:]):
        if a[0] == b[0]: continue
        fraction=(3-a[0])/(b[0]-a[0])
        if 0 <= fraction <= 1:
            crossing=a[1]+fraction*(b[1]-a[1])
            assert abs(crossing)<.6
