from itertools import combinations, product
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import csc_matrix
import numpy as np, json, time, sys
V=range(12)
FOURS=list(combinations(V,4)); SEVENS=list(combinations(V,7))
FIDX={q:i for i,q in enumerate(FOURS)}
A_rows=[]; A_cols=[]
for j,b in enumerate(SEVENS):
    for q in combinations(b,4): A_rows.append(FIDX[q]); A_cols.append(j)
A_data=np.ones(len(A_rows),dtype=float)
A=csc_matrix((A_data,(A_rows,A_cols)),shape=(len(FOURS),len(SEVENS)))

FIG1_FULL=[
(0,1,4,5,8,9),(0,2,4,6,8,10),(0,3,4,7,8,11),
(0,1,6,7,10,11),(0,2,5,7,9,11),(0,3,5,6,9,10),
(2,3,4,5,10,11),(1,3,4,6,9,11),(1,2,4,7,9,10),
(2,3,6,7,8,9),(1,3,5,7,8,10),(1,2,5,6,8,11)]
FILES=[(0,1,2,3),(4,5,6,7),(8,9,10,11)]
FIG6=[
(0,1,2,3,4,5),(0,1,2,6,7,8),(0,1,2,9,10,11),
(0,3,7,8,10,11),(0,4,5,6,10,11),(0,4,5,7,8,9),
(0,3,4,5,6,9),(1,3,6,8,9,11),(1,4,5,7,9,11),
(1,4,5,6,8,10),(1,3,4,5,7,10),(2,3,6,7,9,10),
(2,4,5,8,9,10),(2,4,5,6,7,11),(2,3,4,5,8,11)]

def validate_link(link):
    assert len(link)==15 and all(len(set(b))==6 for b in link)
    cov=set()
    for b in link: cov.update(combinations(sorted(b),3))
    return len(cov)==220

def residual(link):
    covered=set()
    for b in link: covered.update(combinations(sorted(b),4))
    return [q for q in FOURS if q not in covered]

def solve(link,tlim=60):
    rem=residual(link); idx=[FIDX[q] for q in rem]
    C=LinearConstraint(A[idx,:],lb=np.ones(len(idx)),ub=np.full(len(idx),np.inf))
    t=time.time()
    r=milp(c=np.ones(len(SEVENS)),integrality=np.ones(len(SEVENS)),bounds=Bounds(0,1),constraints=C,
           options={'time_limit':tlim,'mip_rel_gap':0.0,'presolve':True})
    out={'status':int(r.status),'message':r.message,'time':time.time()-t,'residual':len(rem),'fun':None if r.fun is None else float(r.fun)}
    if r.x is not None:
        chosen=[SEVENS[i] for i,x in enumerate(r.x) if x>.5]
        out['chosen']=chosen
    return out

def completion(a,b,c):
    return FIG1_FULL+[tuple(sorted(FILES[0]+a)),tuple(sorted(FILES[1]+b)),tuple(sorted(FILES[2]+c))]

if __name__=='__main__':
    print('fig1',validate_link(completion((4,5),(0,1),(0,1))))
    print('fig6',validate_link(FIG6))
    tests=[('fig6',FIG6),('c0',completion((4,5),(0,1),(0,1))),('c1',completion((8,9),(0,1),(0,1)))]
    for n,l in tests:
        print(n,solve(l,120),flush=True)
