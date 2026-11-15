import numpy as np
from beyond_recovery.navigation import GridNavigator
from beyond_recovery.scenarios import box


def test_map_baseline_goes_around_a_wall_instead_of_driving_into_it():
    task={'waypoints':[[5.,0.]],'speed':.4,'fixtures':[box(2,0,.5,.2,1.,.5)],'walls':[]}
    nav=GridNavigator(task)
    path=nav.plan(np.array([0.,0.]),np.array([5.,0.]))
    assert path and max(abs(p[1]) for p in path)>1.2
    assert all(not nav.collides(p,nav.radius) for p in path)


def test_map_baseline_retains_a_narrow_but_nominally_feasible_corridor():
    task={'waypoints':[[5.5,0]],'speed':.4,'fixtures':[
        box(2.3,.525,.55,1.,.15,.55),box(2.3,-.525,.55,1.,.15,.55)],'walls':[]}
    nav=GridNavigator(task)
    path=nav.plan(np.array([0.,0.]),np.array([5.5,0.]))
    assert path and max(abs(p[1]) for p in path)<.2


def test_low_trip_hazards_are_not_silently_avoided_in_contact_tests():
    task={'waypoints':[[5.5,0]],'speed':.4,'fixtures':[box(2.1,0,.065,.22,.28,.065)],'walls':[]}
    nav=GridNavigator(task)
    np.testing.assert_allclose(nav.command([0,0],0,[5.5,0],1),[.4,0,0])
