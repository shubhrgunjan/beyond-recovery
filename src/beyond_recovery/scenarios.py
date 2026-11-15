"""Physical pilot scenes with explicit questions, tasks and disturbance schedules."""
from copy import deepcopy


def box(x, y, z, hx, hy, hz, color=(.42, .48, .55, 1), **kw):
    return dict(center=[x, y, z], half_size=[hx, hy, hz], color=list(color), **kw)


def rack(x, y):
    result = [box(x, y, .06, 1.4, .35, .06, (.25,.31,.38,1))]
    for height in (.55, 1.1, 1.65):
        result.append(box(x,y,height,1.4,.35,.035,(.30,.38,.46,1)))
    for dx in (-1.32, 1.32):
        result.append(box(x+dx,y,.85,.04,.35,.85,(.20,.27,.34,1)))
    for dx in (-.8, 0, .8):
        result.append(box(x+dx,y,.76,.25,.27,.17,(.66,.48,.29,1)))
    return result


def desk(x,y):
    return [box(x,y,.76,.65,.40,.04,(.66,.55,.41,1)),
            *[box(x+dx,y+dy,.36,.035,.035,.36,(.29,.34,.40,1))
              for dx in (-.56,.56) for dy in (-.31,.31)]]


def scenarios():
    base = dict(duration=150., speed=.4, arrival_radius=.25, dwell=1.5,
                settle=2., walls=[], fixtures=[], pushes=[],
                reset_jitter={'position': .015, 'yaw': .015})
    rows = []
    def add(id, title, question, description, **kw):
        row = deepcopy(base)
        row.update(id=id, name=id, title=title, question=question,
                   description=description, **kw)
        rows.append(row)
    add('open_floor', '01 · Open-floor reference',
        'Can the policy complete a multi-stage task before we add constraints?',
        'A clear lab floor. Establish walking, turning and stopping performance.',
        waypoints=[[3,0],[3,3],[0,3],[0,0]], labels=['Station A','Station B','Station C','Home'])
    furniture = rack(3,1.05) + rack(3,-1.05) + [box(6,2,.35,.4,.4,.35,(.60,.43,.25,1))]
    add('warehouse_aisle', '02 · Warehouse aisle',
        'Does limited stepping space make the same disturbance harder to survive?',
        'Walk between physical storage racks, visit a loading station, and return.',
        waypoints=[[5.3,0],[6.8,0],[6.8,3],[0,3],[0,0]],
        labels=['Through the aisle','Loading station','Exit','Return lane','Home'],
        fixtures=furniture,
        pushes=[dict(time=8.,duration=.2,force=[0,70,0],label='Lateral aisle push')])
    add('warehouse_detour', '03 · Warehouse detour',
        'Does taking a longer open route leave more room for a corrective step?',
        'The same racks and destination, reached around the open side. Compare with the aisle.',
        waypoints=[[0,-2.5],[5.3,-2.5],[5.3,0],[6.8,0],[6.8,3],[0,3],[0,0]],
        labels=['Open-side entry','Around the racks','Rejoin route','Loading station','Exit','Return lane','Home'],
        fixtures=deepcopy(furniture),
        pushes=[dict(time=8.,duration=.2,force=[0,70,0],label='Matched lateral pulse')])
    office = desk(2,1.1)+desk(4,-1.1)+desk(5.5,2.8)
    office += [box(2,1.9,.25,.25,.25,.25,(.28,.39,.48,1)),
               box(4,-1.9,.25,.25,.25,.25,(.28,.39,.48,1)),
               box(6.7,2.8,.7,.25,.35,.7,(.35,.45,.32,1))]
    add('office_round', '04 · Office service round',
        'Do turns and repeated stops near furniture accumulate execution errors?',
        'Visit three workstations among desks and fixed chair-shaped obstacles.',
        waypoints=[[2,0],[4,0],[5.5,1.6],[0,3.8],[0,0]],
        labels=['Desk A','Desk B','Desk C','Clear return','Home'], fixtures=office)
    doorway = [box(3,2,.9,.12,1.4,.9,(.53,.57,.60,1)),
               box(3,-2,.9,.12,1.4,.9,(.53,.57,.60,1)),
               box(3,0,2.05,.12,.6,.15,(.53,.57,.60,1))]
    add('doorway', '05 · Narrow doorway',
        'What happens when a correction is needed while crossing a tight boundary?',
        'Pass through a 1.2 m doorway, turn at the destination, and come back.',
        waypoints=[[5.5,0],[5.5,2.8],[5.5,0],[0,0]],
        labels=['Cross doorway','Destination','Return to opening','Home'], fixtures=doorway,
        pushes=[dict(time=8.5,duration=.2,force=[0,65,0],label='Doorway lateral push')])
    add('slippery_floor', '06 · Low-friction floor',
        'Does reduced traction remove the ability to correct a modest push?',
        'A raised 1 cm test patch with friction 0.08; blue in the scene. Compare to open floor.',
        waypoints=[[5,0],[5,3],[0,3],[0,0]],
        labels=['Across the patch','Destination','Return','Home'],
        fixtures=[box(2.7,0,.005,1.25,.9,.005,(.18,.55,.67,1),
                      friction=[.08,.005,.0001],priority=3)],
        pushes=[dict(time=8.,duration=.18,force=[0,60,0],label='Push on low traction')])
    add('compound', '07 · Compound disturbance',
        'Can two events overwhelm a policy that handles a smaller event alone?',
        'Two sequential force pulses between storage racks. Exploratory stress test.',
        waypoints=[[5.3,0],[6.8,0],[6.8,3],[0,3],[0,0]],
        labels=['Through the aisle','Loading station','Exit','Return','Home'],
        fixtures=deepcopy(furniture),
        pushes=[dict(time=7.,duration=.25,force=[0,160,0],label='Lateral pulse'),
                dict(time=7.5,duration=.25,force=[-160,0,0],label='Second: backwards pulse')])
    add('endurance', '08 · Long-horizon endurance',
        'Does task performance remain consistent over repeated phases without resets?',
        'Three consecutive rounds and twelve subgoals, with no intermediate reset.',
        duration=180., waypoints=[[3,0],[3,3],[0,3],[0,0]]*3,
        labels=[f'Round {i+1} · {n}' for i in range(3) for n in ['A','B','C','Home']])
    course=[[5.5,0],[5.5,2.5],[0,2.5],[0,0]]
    labels=['Cross the hazard','Clear destination','Return lane','Home']
    add('hazard_control','00 · Flat hazard-course control',
        'Can the same controller finish this route before a physical hazard is added?',
        'The exact route used by the rough-floor and trip tests, on a clear flat surface.',
        waypoints=deepcopy(course),labels=labels)
    tiles=[]
    for ix in range(9):
        for iy in range(3):
            top=.018+((ix*7+iy*11)%6)*.009
            tiles.append(box(1.1+ix*.40,(iy-1)*.42,top/2,.19,.20,top/2,
                             (.47+.025*(ix%3),.48,.45,1),label='Uneven paving slab'))
    add('rough_pavement','09 · Broken pavement / rough floor',
        'Do repeated uneven foot contacts cause a recoverable stumble or a cascading fall?',
        'A real collision surface of staggered paving slabs, 1.8–6.3 cm high. No artificial pushes.',
        waypoints=deepcopy(course),labels=labels,fixtures=tiles)
    obstacle=box(2.1,0,.065,.22,.28,.065,(.65,.39,.19,1),label='13 cm trip box')
    add('trip_box_open','10 · Trip over a box · open space',
        'After a foot strikes an obstacle, can the robot recover and resume the original route?',
        'A 13 cm box sits directly in the footpath. The surrounding floor is open for recovery.',
        waypoints=deepcopy(course),labels=labels,fixtures=[deepcopy(obstacle)])
    add('trip_box_constrained','11 · Same trip box · restricted space',
        'Does the same trip become harder to recover from when side-stepping and get-up room disappear?',
        'The identical box and route, between barriers leaving a 0.9 m recovery corridor.',
        waypoints=deepcopy(course),labels=labels,
        fixtures=[deepcopy(obstacle),box(2.3,.6,.55,1.0,.15,.55,(.38,.44,.48,1),label='Recovery-space barrier'),
                  box(2.3,-.6,.55,1.0,.15,.55,(.38,.44,.48,1),label='Recovery-space barrier')])
    add('overhead_strike','12 · Low beam / head strike',
        'Does the head contact a low obstruction, and what happens after the impact?',
        'A physical overhead beam starts at 1.24 m, below the upright head clearance. This probes missing ducking or avoidance skills as well as the impact response.',
        waypoints=deepcopy(course),labels=labels,
        fixtures=[box(2.5,0,1.34,.18,.85,.10,(.83,.61,.18,1),label='Low overhead beam'),
                  box(2.5,.93,.77,.09,.09,.77,(.32,.35,.37,1),label='Beam support'),
                  box(2.5,-.93,.77,.09,.09,.77,(.32,.35,.37,1),label='Beam support')])
    steps=[]
    for x,top in [(1.3,.06),(1.9,.12),(2.5,.18),(3.1,.18),(3.7,.12),(4.3,.06)]:
        steps.append(box(x,0,top/2,.30,.75,top/2,(.48,.49,.48,1),label='Raised loading step'))
    add('loading_steps','13 · Loading steps / curb descent',
        'Can the controller handle changes in support height and a step-down without losing the task?',
        'Three 6 cm rises followed by a descent. These are physical steps, not decorative tiles.',
        waypoints=deepcopy(course),labels=labels,fixtures=steps)
    order=['hazard_control','rough_pavement','trip_box_open','trip_box_constrained','overhead_strike','loading_steps',
           'slippery_floor','open_floor','compound','warehouse_aisle','warehouse_detour','office_round','doorway','endurance']
    ordered=sorted(rows,key=lambda row:order.index(row['id']))
    for index,row in enumerate(ordered):
        row['title']=f'{index+1:02} · '+row['title'].split(' · ',1)[1]
    return ordered


def get_scenario(id):
    return deepcopy(next(row for row in scenarios() if row['id'] == id))
