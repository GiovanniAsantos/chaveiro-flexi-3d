#!/usr/bin/env python3
"""Chaveiro flexi print-in-place: corte na base, 2 juntas escondidas, tunel p/ argola.
Uso:
  python3 flexi_chaveiro.py IN.stl OUT.stl --zb=-9.5 --cut=-19:4.5 --cut=4:6.5 --ring=34:-1.9  (use "=" p/ valores negativos)
  --cut X:R  (eixo da junta em x, raio do cilindro interno; frente = -x)
  --ring X:Z (centro do toro do tunel; eixo do toro ao longo de x)
Requer: pip install trimesh manifold3d scipy scikit-image matplotlib shapely rtree
Modelo deve estar de brucos, Z pra cima, cabeca em -x.
"""
import argparse, numpy as np, trimesh
from trimesh.creation import cylinder, box, extrude_polygon, torus
from shapely.geometry import Polygon
from scipy import ndimage
from skimage import measure
from matplotlib.path import Path

def bo(ms, op): return getattr(trimesh.boolean, op)(ms, engine='manifold')
I = lambda a, b: bo([a, b], 'intersection')
U = lambda *a: bo(list(a), 'union')
D = lambda a, b: bo([a, b], 'difference')
BIG = 200

ap = argparse.ArgumentParser()
ap.add_argument('inp'); ap.add_argument('out')
ap.add_argument('--zb', type=float, required=True, help='z do corte da base')
ap.add_argument('--cut', action='append', required=True)
ap.add_argument('--ring', required=True)
ap.add_argument('--gap', type=float, default=0.45)
ap.add_argument('--vang', type=float, default=9.0, help='meio-angulo do V (graus)')
ap.add_argument('--cap', type=float, default=2.4)
ap.add_argument('--round', type=float, default=1.0)
ap.add_argument('--ring_R', type=float, default=3.6)
ap.add_argument('--ring_r', type=float, default=1.5)
a = ap.parse_args()
ZB, G, K = a.zb, a.gap, np.tan(np.radians(a.vang))

def cyl(r, x, z0, z1):
    c = cylinder(radius=r, height=z1 - z0, sections=96); c.apply_translation([x, 0, (z0 + z1) / 2]); return c

def V(xa, off, side):
    Y = 80
    P = ([(xa-BIG,-Y),(xa+off-K*Y,-Y),(xa+off,0),(xa+off-K*Y,Y),(xa-BIG,Y)] if side < 0 else
         [(xa+BIG,-Y),(xa+off+K*Y,-Y),(xa+off,0),(xa+off+K*Y,Y),(xa+BIG,Y)])
    w = extrude_polygon(Polygon(P), BIG); w.apply_translation([0, 0, -BIG/2]); return w

def top_rim(mesh, xa, R):
    zs = []
    for t in np.linspace(0, 2*np.pi, 24, endpoint=False):
        for f in (0.5, 1.0):
            r = mesh.ray.intersects_location([[xa+f*R*np.cos(t), f*R*np.sin(t), 50]], [[0, 0, -1]])[0]
            if len(r): zs.append(r[:, 2].max())
    return min(zs)

def joint(mesh, xa, R):
    zt = top_rim(mesh, xa, R + G)
    avail = zt - a.cap - ZB - 3*G
    L, T, Uu = avail*0.36, avail*0.36, avail*0.28
    z1 = ZB + L; z2 = z1 + G + T; z3 = z2 + G + Uu; rp = min(2.0, R*0.4)
    print(f'junta x={xa} R={R} L={L:.1f} T={T:.1f} U={Uu:.1f} tampa={zt-z3-G:.1f} pino=Ø{2*rp:.1f}')
    if min(L, T, Uu) < 1.8: print('  AVISO: camada < 1.8 mm, reduza R ou mova o corte')
    C = lambda r, z0, z1_: cyl(r, xa, z0, z1_)
    Areg = U(D(V(xa, 0, -1), C(R+G, z1, z2+G)), C(R, ZB-1, z1), C(R, z2+G, z3), C(rp, z1-0.01, z2+G+0.01))
    Breg = D(U(D(D(V(xa, G, 1), C(R+G, ZB-1, z1+G)), C(R+G, z2, z3+G)), C(R, z1+G, z2)), C(rp+G, z1, z2+G))
    return I(mesh, Areg), I(mesh, Breg)

def round_zone(part, xc, r, half=5.0, vox=0.2):
    lo, hi = part.bounds
    lo = np.array([max(lo[0], xc-half-2), lo[1]-2, lo[2]-2]); hi = np.array([min(hi[0], xc+half+2), hi[1]+2, hi[2]+2])
    if hi[0] <= lo[0]: return part
    ax = [np.arange(lo[i], hi[i]+vox, vox) for i in range(3)]
    YY, ZZ = np.meshgrid(ax[1], ax[2], indexing='ij'); pts = np.c_[YY.ravel(), ZZ.ravel()]
    ins = np.zeros([len(q) for q in ax], bool)
    for i, x in enumerate(ax[0]):
        sec = part.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
        if sec is None: continue
        acc = np.zeros(len(pts), int)
        for e in sec.discrete: acc += Path(e[:, 1:3]).contains_points(pts)
        ins[i] = (acc % 2 == 1).reshape(YY.shape)
    er = ndimage.distance_transform_edt(ins)*vox > r
    field = ndimage.distance_transform_edt(~er)*vox - r
    field = ndimage.gaussian_filter(field, 0.4); field[0] = field[-1] = 1.0
    field = np.pad(field, 1, constant_values=1.0)
    v, f, _, _ = measure.marching_cubes(field, 0.0, spacing=(vox,)*3, allow_degenerate=False)
    om = trimesh.Trimesh(v - vox + lo, f, process=True); om.merge_vertices(); om.fix_normals()
    if om.volume < 0: om.invert()
    if not om.is_volume: om.fill_holes(); om.fix_normals()
    if not om.is_volume:
        print(f'  aviso: arredondamento pulado em x={xc}'); return part
    zone = box(bounds=[[xc-half, -BIG, -BIG], [xc+half, BIG, BIG]])
    return U(D(part, zone), I(I(part, zone), om))

m = trimesh.load(a.inp)
m = I(m, box(bounds=[[-BIG, -BIG, ZB], [BIG, BIG, BIG]]))
print('area da base ~', round(sum(p.area for p in m.section(plane_origin=[0,0,ZB+0.05],plane_normal=[0,0,1]).to_2D()[0].polygons_full)), 'mm2')
cuts = sorted([tuple(map(float, c.split(':'))) for c in a.cut])
parts, rest = [], m
for xa, R in cuts:
    p, rest = joint(rest, xa, R); parts.append(p)
parts.append(rest)
rx, rz = map(float, a.ring.split(':'))
t = torus(major_radius=a.ring_R, minor_radius=a.ring_r, major_sections=96, minor_sections=32)
t.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0, 1, 0])); t.apply_translation([rx, 0, rz])
parts[-1] = D(parts[-1], t)
for i, p in enumerate(parts):
    for xc, _ in cuts:
        if p.bounds[0, 0]-6 < xc < p.bounds[1, 0]+6: p = round_zone(p, xc, a.round)
    parts[i] = p
ok = True
for i, p in enumerate(parts):
    nb = len(p.split(only_watertight=False))
    print(f'parte {i}: watertight={p.is_watertight} corpos={nb} vol={p.volume:.0f}')
    ok &= p.is_watertight and nb == 1
for i in range(len(parts)-1):
    x = I(parts[i], parts[i+1]); ov = x.volume if len(x.faces) else 0
    print(f'sobreposicao {i}-{i+1}: {ov:.3f}'); ok &= ov < 1e-3
for i, p in enumerate(parts): p.export(a.out.replace('.stl', f'_parte{i}.stl'))
trimesh.util.concatenate(parts).export(a.out)
print('OK' if ok else 'FALHOU — revisar', '->', a.out)
