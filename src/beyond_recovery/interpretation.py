"""Evidence-bounded, rule-based interpretation of a completed trial."""
import math


def interpret(task,rows,result,fall_events,contact_events,controller,manual):
    duration=rows[-1]['time'] if rows else 0
    phase=max((r['phase'] for r in rows),default=0)
    head=max((r.get('head_contact_n',0) for r in rows),default=0)
    body=max((r.get('body_contact_n',0) for r in rows),default=0)
    saturated=sum(r.get('effort',0)>95 for r in rows)*.02
    recovery=sum(e.get('recovered_at') is not None for e in fall_events)
    resumed=sum(e.get('task_resumed_at') is not None for e in fall_events)
    observations=[f'{phase}/{len(task["waypoints"])} subgoals completed over {duration:.2f} simulated seconds.',
                  f'{len(fall_events)} balance-loss episodes; {recovery} returned to a sustained upright stance.',
                  f'{resumed} recovery episodes were followed by advancement of the original task subgoal.',
                  f'Actuator use exceeded 95% for {saturated:.2f} seconds.']
    limitations=['One simulation trial does not establish statistical significance or novelty.',
                 'Contact-force peaks depend on timestep, contact stiffness and geometry; they are not injury or damage estimates.',
                 'A static support margin is not a dynamic recoverability certificate.']
    if contact_events:
        first=contact_events[0]
        observations.append(f'First measured hazard contact: {first["label"]} at {first["time"]:.2f} s ({first["region"]}).')
    else: observations.append('No contact with the configured hazard was measured; this trial does not demonstrate a collision response.')
    if head>0: observations.append(f'Peak measured head contact force: {head:.1f} N.')
    if body>0: observations.append(f'Peak measured non-foot body contact force: {body:.1f} N.')
    if duration<2:
        headline='Too little execution to assess the hazard'
        importance='Insufficient evidence'
        meaning='The trial ended before a meaningful task or hazard interaction. Keep the saved data, but do not infer a recovery limitation.'
        next_test='Run the complete test or continue until the robot has encountered the hazard.'
    elif task['id']=='overhead_strike' and head>1:
        headline='A physical head strike was measured'
        importance='Important capability gap; not yet evidence of recovery-option loss'
        meaning='The walking controller did not avoid or duck under a low obstruction. This first indicates missing clearance perception/planning or a ducking skill. Post-impact recovery is a separate question.'
        next_test='Compare with a reachable route around the beam or a controller with a validated ducking behavior; then compare post-impact task resumption.'
    elif fall_events and recovery:
        headline=('The robot recovered and advanced its original task' if resumed else
                  'The robot stood up, but task resumption was not observed')
        if recovery<len(fall_events):headline='Some balance-loss episodes recovered; others did not'
        importance='Useful recovery evidence'
        meaning='The recovery controller produced a physical return to standing without a state reset. Standing alone is not task recovery; inspect whether the original subgoal advanced afterward.'
        next_test='Repeat the same hazard, controller, seed and speed with less surrounding recovery space. Compare recovery time and subsequent subgoal completion.'
    elif fall_events:
        headline='The hazard or disturbance led to balance loss without successful recovery'
        importance='Useful failure case; cause still needs a controlled comparison'
        meaning=('The walking-only baseline has no trained get-up behavior, so failure to stand cannot establish that all recovery options were physically impossible.' if controller=='reference' else
                 'The experimental learned recovery controller did not regain a sustained upright stance within the observation window. This is evidence about this controller in this state, not proof that no recovery strategy exists.')
        next_test='Compare the identical trial on clear flat ground and the open-space versus constrained-space trip pair. Use multiple seeds and verify the nominal task is otherwise feasible.'
    elif result=='timeout' and rows and duration>=10 and not fall_events and math.hypot(rows[-1]['x']-next(r for r in rows if r['time']>=duration-10)['x'],rows[-1]['y']-next(r for r in rows if r['time']>=duration-10)['y'])<.15:
        headline='The robot remained upright but task execution stalled'
        importance='Baseline control or navigation needs diagnosis'
        meaning='There was no detected balance loss and little net movement over the final ten seconds. Check turning, arrival dwell and obstruction handling before interpreting this as a physical recovery limitation.'
        next_test='Compare the clear-floor route with turn/arrival tuning, then compare direct waypoint following with the static-map planner under the same controller and seed.'
    elif result=='success':
        headline='The controller completed the task under this test condition'
        importance='Useful baseline; no observed failure in this run'
        meaning='The measured task was feasible for this controller. Success does not tell us how much recovery capacity remained before the next disturbance.'
        next_test='Increase hazard difficulty gradually or apply the same bounded disturbance at matched task progress. Compare completion and post-disturbance resumption.'
    else:
        headline='The task was interrupted or did not finish'
        importance='Diagnostic result'
        meaning='A timeout or stop can reflect route obstruction, a missing skill or operator intervention rather than a recovery failure. Inspect contacts and progress before attributing the result.'
        next_test='Check a clear-floor control with the same route and controller, then isolate one hazard at a time.'
    if manual:
        limitations.insert(0,'Manual driving or pushes were used. This is an intervention trial, not an autonomous-policy benchmark.')
    if controller=='amp':
        limitations.append('The experimental AMP profile uses its published gains, armature and torque limits. Compare hazards within this profile; do not attribute differences from the reference profile solely to recovery learning.')
    if task['id'] in ('rough_pavement','loading_steps'):
        limitations.insert(0,'Failure on terrain may indicate a locomotion skill/distribution gap. It does not by itself establish the proposed recovery-preservation problem.')
    relevance='This establishes a baseline failure mode. Recovery preservation is only isolated when the nominal task is feasible and the same controller is compared under controlled changes in recovery opportunity.'
    if task['id'] in ('trip_box_open','trip_box_constrained'):
        relevance='This is a direct probe of our proposed problem: the same trip hazard is tested with and without surrounding recovery space. A matched pair can reveal how constraints change the controller response. Barriers can also supply physical support; less free space does not necessarily mean worse recovery. One failed attempt does not establish that every possible recovery was unavailable.'
        next_test='Run the other member of the open/constrained trip pair with the same controller, speed, seed and interventions. Compare contact timing, time to stand, and advancement of the original subgoal after recovery; then repeat over seeds.'
    elif task['id']=='overhead_strike':
        relevance='This mainly tests clearance awareness and a missing ducking/avoidance skill. It becomes relevant to recovery preservation when earlier task decisions could have kept a feasible alternative route or recovery posture available.'
    elif task['id'] in ('rough_pavement','loading_steps'):
        relevance='This checks whether the baseline has enough locomotion competence for the later study. If it cannot traverse ordinary terrain at all, we must improve that baseline before claiming a recovery-preservation contribution.'
    return dict(headline=headline,importance=importance,meaning=meaning,observations=observations,
                research_relevance=relevance,next_test=next_test,limitations=limitations,method='Rule-based interpretation of measured trial data',
                controller=controller,head_contact_peak_n=head,body_contact_peak_n=body,
                falls=fall_events,hazard_contacts=contact_events)


def markdown(report):
    text=f'# {report["headline"]}\n\n**Assessment:** {report["importance"]}\n\n{report["meaning"]}\n\n## Measured observations\n\n'
    text+=''.join('- '+x+'\n' for x in report['observations'])
    text+='\n## Why it matters for this project\n\n'+report['research_relevance']
    text+='\n\n## Next experiment\n\n'+report['next_test']+'\n\n## Limits\n\n'
    text+=''.join('- '+x+'\n' for x in report['limitations'])
    return text
