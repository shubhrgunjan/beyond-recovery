"""Classical perfect-map A* baseline used to test a navigation confound.

This is not a recoverability estimator. Low trip hazards/terrain are intentionally
not treated as walls; operators can compare contact response with map replanning.
"""
import heapq,math
import numpy as np
from beyond_recovery.task import wrap


class GridNavigator:
    def __init__(self,task,radius=.23,resolution=.10):
        self.task=task;self.radius=radius;self.resolution=resolution
        self.obstacles=[f for f in task.get('walls',[])+task.get('fixtures',[])
                        if f['center'][2]+f['half_size'][2]>.30 and f['center'][2]-f['half_size'][2]<1.35]
        points=[(0,0),*task['waypoints'],*[f['center'][:2] for f in self.obstacles]]
        a=np.array(points);self.low=np.floor((a.min(axis=0)-2)/resolution)*resolution
        self.high=np.ceil((a.max(axis=0)+2)/resolution)*resolution
        self.shape=tuple((np.round((self.high-self.low)/resolution).astype(int)+1).tolist())
        self.blocked=np.zeros(self.shape,dtype=bool)
        for ix in range(self.shape[0]):
            for iy in range(self.shape[1]):
                self.blocked[ix,iy]=self.collides(self.world((ix,iy)),radius)
        self.path=[];self.goal=None;self.next_update=-1;self.no_path=0;self.replans=0

    def world(self,cell):return self.low+np.array(cell)*self.resolution
    def cell(self,p):return tuple(np.round((np.asarray(p)-self.low)/self.resolution).astype(int))
    def inside(self,p):return all(0<=p[i]<self.shape[i] for i in (0,1))
    def collides(self,p,radius):
        return any(np.all(np.abs(np.asarray(p)-f['center'][:2])<=np.asarray(f['half_size'][:2])+radius)
                   for f in self.obstacles)
    def visible(self,a,b,radius):
        n=max(2,int(np.linalg.norm(np.asarray(a)-b)/(self.resolution/2))+1)
        return not any(self.collides(p,radius) for p in np.linspace(a,b,n))

    def snap(self,p):
        start=self.cell(p)
        if self.inside(start) and not self.blocked[start]:return start
        choices=[]
        for dx in range(-10,11):
            for dy in range(-10,11):
                c=(start[0]+dx,start[1]+dy)
                if self.inside(c) and not self.blocked[c] and self.visible(p,self.world(c),0.):
                    choices.append((np.linalg.norm(self.world(c)-p),c))
        return min(choices)[1] if choices else None

    def plan(self,start,goal):
        a=self.snap(start);b=self.snap(goal);self.replans+=1
        if a is None or b is None:self.no_path+=1;return []
        frontier=[(0.,a)];came={};cost={a:0.}
        directions=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
        while frontier:
            _,current=heapq.heappop(frontier)
            if current==b:
                cells=[b]
                while cells[-1]!=a:cells.append(came[cells[-1]])
                return [self.world(c) for c in reversed(cells)]+[np.array(goal,dtype=float)]
            for dx,dy in directions:
                nxt=(current[0]+dx,current[1]+dy)
                if not self.inside(nxt) or self.blocked[nxt]:continue
                if dx and dy and (self.blocked[current[0]+dx,current[1]] or self.blocked[current[0],current[1]+dy]):continue
                new=cost[current]+math.hypot(dx,dy)
                if new<cost.get(nxt,float('inf')):
                    cost[nxt]=new;came[nxt]=current
                    heuristic=math.hypot(nxt[0]-b[0],nxt[1]-b[1])
                    heapq.heappush(frontier,(new+heuristic,nxt))
        self.no_path+=1;return []

    def command(self,xy,yaw,goal,time):
        xy=np.array(xy);goal=np.array(goal)
        if not self.obstacles or self.visible(xy,goal,self.radius):
            target=goal
        else:
            if self.goal is None or np.linalg.norm(goal-self.goal)>1e-6 or time>=self.next_update or not self.path:
                self.path=self.plan(xy,goal);self.goal=goal.copy();self.next_update=time+.4
            if not self.path:return np.zeros(3)
            while len(self.path)>1 and np.linalg.norm(self.path[0]-xy)<.13:self.path.pop(0)
            target=self.path[0]
            for point in self.path:
                if np.linalg.norm(point-xy)>.65:break
                if self.visible(xy,point,self.radius):target=point
        delta=target-xy
        if np.linalg.norm(delta)<1e-5:return np.zeros(3)
        error=wrap(math.atan2(delta[1],delta[0])-yaw)
        speed=min(self.task['speed'],np.linalg.norm(goal-xy))*max(0.,math.cos(error))
        if abs(error)>.6:speed=0.
        return np.array([speed,0.,np.clip(1.3*error,-.5,.5)])
