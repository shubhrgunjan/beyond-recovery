import numpy as np

from beyond_recovery.task import Route, average_force, wall_clearance


def test_disturbance_impulse_survives_non_aligned_step_boundaries():
    events = [{"time": 0.031, "duration": 0.117, "force": [0, 60, 0]}]
    impulse = sum((average_force(events, i * .02, .02) * .02 for i in range(20)),
                  np.zeros(3))
    np.testing.assert_allclose(impulse, [0, 60 * .117, 0])


def test_route_requires_continuous_dwell_and_finishes_once():
    route = Route({"waypoints": [[1, 0]], "speed": .4, "settle": 0,
                   "dwell": .2, "arrival_radius": .1})
    route.command([1, 0], 0, 0, .1)
    route.command([0, 0], 0, .1, .1)
    assert route.dwell_elapsed == 0
    assert route.command([0, 0], np.pi, .2, .1)[0] == 0
    route.command([1, 0], 0, .3, .1)
    route.command([1, 0], 0, .4, .1)
    assert route.complete and route.phase == 1
    np.testing.assert_array_equal(route.command([2, 0], 0, .5, .1), [0, 0, 0])


def test_wall_clearance_uses_physical_surface():
    walls = [{"center": [0, 1, .5], "half_size": [2, .1, .5]}]
    assert abs(wall_clearance([0, 0], walls) - .9) < 1e-12
    assert wall_clearance([0, 1], walls) < 0


def test_centered_arrival_keeps_approaching_inside_the_dwell_boundary():
    route=Route({'waypoints':[[1,0]],'speed':.4,'settle':0,'dwell':1.,'arrival_radius':.25,'arrival_mode':'centered'})
    assert route.command([.78,0],0,0,.1)[0]>0
    np.testing.assert_array_equal(route.command([.95,0],0,.1,.1),[0,0,0])
    route.command([.7,0],0,.2,.1)
    assert route.dwell_elapsed==0
    for i in range(11):route.command([1.,0],0,.3+i*.1,.1)
    assert route.complete and route.phase==1
