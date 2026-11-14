import zipfile, re, numpy as np, trimesh
import sys
stl=sys.argv[1]
tmf=sys.argv[2]
m=trimesh.load(stl, force='mesh')
t=zipfile.ZipFile(tmf).read('3D/3dmodel.model').decode()
cents=[]; cols=[]
for o in re.finditer(r'<object id="\d+" name="(\w+)"[^>]*pindex="(\d+)"><mesh>(.*?)</mesh>',t,re.S):
    V=np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"',o.group(3)),float)
    F=np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"',o.group(3)),int)
    cents.append(V[F].mean(1)); cols+=[int(o.group(2))]*len(F)
cents=np.concatenate(cents); cols=np.array(cols)
from scipy.spatial import cKDTree
col=cols[cKDTree(cents).query(m.triangles_center)[1]]
# one colour per connected part, by area-weighted vote, so no part comes out speckled
lab=trimesh.graph.connected_component_labels(m.face_adjacency, node_count=len(m.faces))
for l in np.unique(lab):
    idx=lab==l; col[idx]=np.bincount(col[idx],weights=m.area_faces[idx],minlength=4).argmax()
    if m.triangles_center[idx][:,2].min()>960 and idx.sum() in (405,406,288): col[idx]=2
    if m.triangles_center[idx][:,2].min()>900: print('headrest part',idx.sum(),col[idx][0])
V=m.vertices/1000.0; R=np.stack([V[:,1]-0.400, V[:,2], V[:,0]-0.3645],1)
R2=np.sqrt(.5); CP=np.cos(0.6155); SP=np.sin(0.6155); view=np.array([-0.577,0.577,-0.577])
S=2600
u=(R[:,0]-R[:,2])*R2*S; v=-(R[:,1]*CP+(R[:,0]+R[:,2])*R2*SP)*S; d=R@view
u-=u.min()-2; v-=v.min()-2
Wp=int(u.max())+4; Hp=int(v.max())+4
zb=np.full((Hp,Wp),-1e9); ib=np.full((Hp,Wp),-1,int)
F=m.faces
for i,(a,b,c) in enumerate(F):
    xs=u[[a,b,c]]; ys=v[[a,b,c]]; ds=d[[a,b,c]]
    x0=int(np.floor(xs.min())); x1=int(np.ceil(xs.max())); y0=int(np.floor(ys.min())); y1=int(np.ceil(ys.max()))
    den=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
    if abs(den)<1e-9: continue
    gx,gy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
    w0=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/den
    w1=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/den
    w2=1-w0-w1
    ins=(w0>=-1e-6)&(w1>=-1e-6)&(w2>=-1e-6)
    z=w0*ds[0]+w1*ds[1]+w2*ds[2]
    sub=zb[y0:y1+1,x0:x1+1]; si=ib[y0:y1+1,x0:x1+1]
    win=ins&(z>sub); sub[win]=z[win]; si[win]=i
vis=np.unique(ib[ib>=0])
print(len(F),'->',len(vis))
Fv=F[vis]; cv=col[vis]
used,inv=np.unique(Fv,return_inverse=True); inv=inv.reshape(-1,3)
Q=np.round(R[used]*1000).astype(int)
js="const CHAIR = { v: ["+",".join(map(str,Q.flatten().tolist()))+"], f: ["+",".join(f"{a},{b},{c},{k}" for (a,b,c),k in zip(inv.tolist(),cv.tolist()))+"] };"
open('chair_data.js','w').write(js); print(len(Q),len(js), np.bincount(cv))
