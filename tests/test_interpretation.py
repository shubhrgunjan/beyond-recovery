from beyond_recovery.interpretation import interpret
from beyond_recovery.scenarios import get_scenario


def test_zero_length_trial_does_not_claim_a_research_finding():
    task=get_scenario('trip_box_open')
    report=interpret(task,[dict(time=0,phase=0)],'stopped',[],[],'amp',False)
    assert report['importance']=='Insufficient evidence'


def test_head_strike_points_to_clearance_skill_before_claiming_recovery_novelty():
    task=get_scenario('overhead_strike')
    report=interpret(task,[dict(time=10,phase=0,head_contact_n=150)],'stopped',[],
                     [dict(time=9,label='Low overhead beam',region='head')],'amp',False)
    assert 'clearance' in report['meaning']
    assert 'not yet' in report['importance']


def test_walking_only_failure_does_not_establish_physical_unrecoverability():
    task=get_scenario('trip_box_open')
    report=interpret(task,[dict(time=25,phase=0)],'recovery_failed',
                     [dict(start=5,recovered_at=None)],[],'reference',False)
    assert 'no trained get-up' in report['meaning']


def test_recovery_is_separate_from_task_resumption():
    report=interpret(get_scenario('trip_box_open'),[dict(time=15,phase=0)],'stopped',
                     [dict(start=5,recovered_at=10)],[],'amp',True)
    assert any('0 recovery episodes' in x for x in report['observations'])
    assert any('Manual' in x for x in report['limitations'])
