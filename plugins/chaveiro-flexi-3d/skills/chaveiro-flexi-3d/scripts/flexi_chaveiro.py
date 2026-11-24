#!/usr/bin/env python3
"""Chaveiro flexi print-in-place: corte na base, 2 juntas escondidas (3 partes), tunel p/ argola.

Subcomandos:
  analyze IN.stl [--rot z:180] [--length 100] [--joint pino|bola|elos] [--png perfil.png]
      -> perfil, vistas e linha de comando sugerida para o build
  build IN.stl OUT.stl --zb=Z --cut=X:R --cut=X:R --ring=X:Z [--joint pino|bola|elos]
        [--yaw 18] [--pitch 12] [--preview DIR] [--rot ...] [--length ...]

Convencoes (depois de --rot/--length o modelo e centrado: x,y no meio, z min = 0):
  de brucos, Z pra cima, cabeca em -x, comprimento em x.
  --cut X:R  X = posicao da emenda no eixo x; R = tamanho da junta
             pino: raio do cilindro interno | bola: raio da bola | elos: R*0.55 = espessura do arame
  --ring X:Z centro do toro do tunel (eixo do toro ao longo de x)
  Use "=" em valores negativos (--zb=-9.5).
Juntas:
  pino  lajes + lingueta + pino vertical (padrao aprovado). --pitch>0 abre folga varrida p/ inclinar.
  bola  bola truncada apoiada na mesa, pescoco horizontal, soquete varrido. Gira e inclina.
  elos  2 argolas entrelacadas (uma deitada na parte da frente, uma em pe na de tras). Gira, inclina, tem folga.
Requer: pip install trimesh manifold3d scipy scikit-image matplotlib shapely rtree fast-simplification
"""
import argparse, os, sys, numpy as np, trimesh
from trimesh.creation import cylinder, box, extrude_polygon, torus, icosphere, cone
from trimesh.transformations import rotation_matrix
from shapely.geometry import Polygon
from shapely.ops import unary_union
from scipy import ndimage
from skimage import measure
from matplotlib.path import Path

BIG = 400
COLS = ['#e07a5f', '#81b29a', '#3d405b', '#f2cc8f']


def bo(ms, op): return getattr(trimesh.boolean, op)(ms, engine='manifold', check_volume=False)
def I(a, b): return bo([a, b], 'intersection')
def U(*a): return a[0] if len(a) == 1 else bo(list(a), 'union')
def D(a, b): return bo([a, b], 'difference')
def die(msg): print('ERRO:', msg); sys.exit(1)
def halfspace(x0=-BIG, x1=BIG, z0=-BIG, z1=BIG): return box(bounds=[[x0, -BIG, z0], [x1, BIG, z1]])


# ---------------------------------------------------------------- modelo
def load_model(a):
    m = trimesh.load(a.inp, force='mesh')
    if m is None or m.is_empty: die(f'nao consegui ler malha de {a.inp}')
    m.merge_vertices()
    if not m.is_watertight:
        m.fill_holes(); m.fix_normals()
    if not m.is_watertight: die('malha nao e fechada (watertight). Reparar antes (ex.: Bambu Studio > Reparar).')
    for spec in a.rot or []:
        ax, deg = spec.split(':')
        m.apply_transform(rotation_matrix(np.radians(float(deg)), {'x': [1, 0, 0], 'y': [0, 1, 0], 'z': [0, 0, 1]}[ax]))
    if a.length:
        m.apply_scale(a.length / m.extents[0])
    lo, hi = m.bounds
    m.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    if m.volume < 0: m.invert()
    return m


def skin_top(m, x, y=0.0):
    r = m.ray.intersects_location([[x, y, m.bounds[1, 2] + 10]], [[0, 0, -1]])[0]
    return r[:, 2].max() if len(r) else None


def halfwidth(m, x):
    s = m.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
    if s is None: return 0.0
    return float(np.abs(s.vertices[:, 1]).max())


def top_rim(m, xa, R):
    zs = []
    for t in np.linspace(0, 2 * np.pi, 24, endpoint=False):
        for f in (0.5, 1.0):
            z = skin_top(m, xa + f * R * np.cos(t), f * R * np.sin(t))
            if z is not None: zs.append(z)
    if not zs: die(f'nao achei o topo do corpo em x={xa:.1f} (corte fora do bicho?)')
    return min(zs)


def wall_min(m, geom2d, zs):
    """Menor parede entre a pegada 2D da junta e a pele, em varias alturas."""
    best = 99.0
    for z in zs:
        s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if s is None: continue
        p, T = s.to_2D()
        pts = np.c_[np.array(geom2d.exterior.coords), np.full(len(geom2d.exterior.coords), z), np.ones(len(geom2d.exterior.coords))]
        loc = (np.linalg.inv(T) @ pts.T).T[:, :2]
        g = Polygon(loc)
        for poly in p.polygons_full:
            if poly.intersects(g):
                best = min(best, poly.exterior.distance(g) if poly.contains(g) else 0.0)
    return best


def inscribed(m, x, z):
    """Distancia do ponto (x,0,z) ate a pele no corte horizontal z."""
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None: return 0.0
    p, T = s.to_2D()
    q = (np.linalg.inv(T) @ np.array([x, 0, z, 1]))[:2]
    from shapely.geometry import Point
    return max([poly.exterior.distance(Point(q)) for poly in p.polygons_full if poly.contains(Point(q))] or [0.0])


def sec_area_z(m, z):
    s = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if s is None: return 0.0
    p, _ = s.to_2D()
    return float(sum(q.area for q in p.polygons_full))


def mrot(c, yaw, pitch):
    """A se move por M: yaw (graus, eixo z) apos pitch (graus, eixo y), ambos pelo pivo c."""
    return rotation_matrix(np.radians(yaw), [0, 0, 1], c) @ rotation_matrix(np.radians(pitch), [0, 1, 0], c)


def grid(nY=7, nP=5):
    ys = np.linspace(-a.yaw, a.yaw, nY) if a.yaw > 0 else [0.0]
    ps = np.linspace(-a.pitch_down, a.pitch_up, nP) if a.pitch_up + a.pitch_down > 0 else [0.0]
    return [(y, p) for y in ys for p in ps]


def moved(mesh, M):
    q = mesh.copy(); q.apply_transform(M); return q


def sweep(mesh, c, inverse=False):
    """Uniao das posicoes de `mesh` ao longo da faixa de movimento."""
    cs = []
    for y, p in grid():
        M = mrot(c, y, p)
        cs.append(moved(mesh, np.linalg.inv(M) if inverse else M))
    return U(*cs)


def carve_front(A, B, c, x0, x1):
    """Tira de A tudo que B (perto da junta) ocuparia em qualquer posicao -> folgas/alivios automaticos."""
    if a.yaw <= 0 and a.pitch_up + a.pitch_down <= 0: return A
    Bl = I(B, halfspace(x0, x1))
    for y, p in grid():                      # uma posicao por vez: memoria baixa (inclui repouso)
        A = D(A, moved(Bl, np.linalg.inv(mrot(c, y, p))))
    return A


# ---------------------------------------------------------------- juntas
def joint_pino(rest, xa, R):
    K = np.tan(np.radians(a.vang))
    def cyl(r, z0, z1):
        cc = cylinder(radius=r, height=z1 - z0, sections=96); cc.apply_translation([xa, 0, (z0 + z1) / 2]); return cc
    def V(off, side):
        Y = 80
        P = ([(xa - BIG, -Y), (xa + off - K * Y, -Y), (xa + off, 0), (xa + off - K * Y, Y), (xa - BIG, Y)] if side < 0 else
             [(xa + BIG, -Y), (xa + off + K * Y, -Y), (xa + off, 0), (xa + off + K * Y, Y), (xa + BIG, Y)])
        w = extrude_polygon(Polygon(P), BIG); w.apply_translation([0, 0, -BIG / 2]); return w
    zt = top_rim(rest, xa, R + G)
    avail = zt - a.cap - ZB - 3 * G
    L, T, Uu = avail * 0.36, avail * 0.36, avail * 0.28
    z1 = ZB + L; z2 = z1 + G + T; z3 = z2 + G + Uu; rp = min(2.0, R * 0.4)
    c = np.array([xa, 0, z1 + G + T / 2])
    tilt = R * np.sin(np.radians(a.pitch))
    print(f'  [pino] x={xa} R={R} L={L:.1f} T={T:.1f} U={Uu:.1f} tampa={zt - z3 - G:.1f} pino=O{2 * rp:.1f}'
          f'  (borda das lajes perde ~{tilt:.1f} mm p/ inclinar)')
    if min(L, T, Uu) < 1.8: print('  AVISO: camada < 1.8 mm, reduza R ou mova o corte')
    from shapely.geometry import Point
    wl = wall_min(rest, Point(xa, 0).buffer(R + G, 64), [(ZB + z1) / 2, (z1 + z2) / 2])
    if wl < 1.5: print(f'  AVISO: parede lateral {wl:.1f} mm (<1.5), reduza R')
    Areg = U(D(V(0, -1), cyl(R + G, z1, z2 + G)), cyl(R, ZB - 1, z1), cyl(R, z2 + G, z3), cyl(rp, z1 - 0.01, z2 + G + 0.01))
    Breg = D(U(D(D(V(G, 1), cyl(R + G, ZB - 1, z1 + G)), cyl(R + G, z2, z3 + G)), cyl(R, z1 + G, z2)), cyl(rp + G, z1, z2 + G))
    A, B = I(rest, Areg), I(rest, Breg)
    A = carve_front(A, B, c, xa - R - G - 3, xa + R + G + 12)
    info = dict(tipo='pino', x=xa, c=c, keep=(xa - R - G, xa + R + G),
                protect=cyl(R + G + 0.8, ZB - 1, z3 + G + 0.4),
                forca=f'pino O{2 * rp:.1f} mm em cisalhamento; lajes {min(L, T, Uu) - tilt:.1f} mm na borda')
    return A, B, info


def joint_bola(rest, xs, Rb):
    wall = 1.6
    rn = float(np.clip(0.42 * Rb, 1.5, 2.6))
    X = xs + Rb + G + wall                       # centro da bola (atras da emenda)
    zt = top_rim(rest, X, Rb + G)
    zc = min(ZB + 0.55 * Rb, zt - a.cap - G - (Rb + G) * np.sqrt(2))
    if zc < ZB + 0.25 * Rb: print(f'  AVISO: corpo baixo demais p/ bola R={Rb}; reduza R')
    c = np.array([X, 0, zc])
    from shapely.geometry import Point
    wl = wall_min(rest, Point(X, 0).buffer(Rb + G, 64), [ZB + 0.5, zc])
    if wl < 1.5: print(f'  AVISO: parede lateral {wl:.1f} mm (<1.5), reduza R')
    def sph(r): s = icosphere(subdivisions=3, radius=r); s.apply_translation(c); return s
    def neck(r, x0):
        n = cylinder(radius=r, height=X - x0, sections=48)
        n.apply_transform(rotation_matrix(np.pi / 2, [0, 1, 0])); n.apply_translation([(X + x0) / 2, 0, zc]); return n
    rc = Rb + G
    roof = cone(radius=rc / np.sqrt(2) + 0.05, height=rc / np.sqrt(2) + 0.05, sections=96)   # teto 45 graus
    roof.apply_translation([X, 0, zc + rc / np.sqrt(2) - 0.05])
    S0 = U(sph(rc), roof, neck(rn + G, xs - 4))
    cav = sweep(S0, c)
    ball = U(sph(Rb), neck(rn, xs - 2.5))
    B = D(I(rest, halfspace(xs + G)), cav)
    A = U(I(rest, halfspace(x1=xs)), I(rest, ball))
    A = carve_front(A, B, c, xs - 6, X + Rb + G + wall + 6)
    sy, sp = np.sin(np.radians(a.yaw)), np.sin(np.radians(a.pitch))
    lip_y = Rb - (rc * sy + rn + G)
    lip_z = Rb - (rc * sp + rn + G)
    cap = zt - (cav.bounds[1, 2])
    print(f'  [bola] emenda x={xs} bola R={Rb} centro=({X:.1f},{zc:.1f}) pescoco=O{2 * rn:.1f} '
          f'trava lateral={lip_y:.1f} trava vertical={lip_z:.1f} tampa~{cap:.1f}')
    if min(lip_y, lip_z) < 1.0: print('  AVISO: trava < 1 mm -> a bola pode escapar ao puxar; aumente R ou reduza --yaw/--pitch')
    pk = U(sph(Rb + G + 1.0), box(bounds=[[xs - 3, -(rn + G + 3), zc - rn - G - 3], [X, rn + G + 3, zc + rn + G + 3]]))
    info = dict(tipo='bola', x=xs, c=c, keep=(xs - 1, X + Rb + G + wall), protect=pk,
                forca=f'pescoco O{2 * rn:.1f} mm; trava da bola {min(lip_y, lip_z):.1f} mm (encaixe, pode estourar)')
    return A, B, info


def joint_elos(rest, xs, R):
    w = float(np.clip(0.55 * R, 1.6, 3.2))       # espessura do arame (quadrado w x w)
    play = 0.8
    d1 = d2 = G + 0.8
    # argola da frente (A): deitada na mesa, perna de tras em ponte sobre a barra de baixo da argola B
    fb0 = xs - d1 - w                             # perna da frente de B: [fb0, fb0+w]
    ha0 = fb0 - G - play                          # furo de A comeca aqui
    xa_root0 = ha0 - w
    xa_far0, xa_far1 = xs + d2, xs + d2 + w       # perna de tras de A (dentro do furo de B)
    hy = w / 2 + G + play                         # meia largura do furo de A
    zA0, zA1 = ZB, ZB + 2 * w + G                 # barras laterais/raiz de A
    zAf0 = ZB + w + G                             # perna de tras de A passa por cima da barra de B
    root_len = 3.0
    bA = [[[xa_root0 - root_len, -(hy + w), zA0], [xa_far1, -hy, zA1]],
          [[xa_root0 - root_len, hy, zA0], [xa_far1, hy + w, zA1]],
          [[xa_root0 - root_len, -(hy + w), zA0], [ha0, hy + w, zA1]],
          [[xa_far0, -(hy + w), zAf0], [xa_far1, hy + w, zA1]]]
    # argola de tras (B): em pe no plano xz, barra de baixo na mesa
    hb1 = xa_far1 + G + play                      # fim do furo de B
    xb_back1 = hb1 + w
    hz_top = zA1 + G + play + 0.6                 # topo do furo de B
    zB1 = hz_top + w
    zt = top_rim(rest, (fb0 + xb_back1) / 2, max(w, (xb_back1 - xa_root0) / 2))
    if zB1 + G + a.cap > zt: print(f'  AVISO: elos altos demais (precisa {zB1 + G + a.cap - ZB:.1f} mm de altura); reduza R')
    yb = w / 2
    bB = [[[fb0, -yb, ZB], [xb_back1 + root_len, yb, ZB + w]],
          [[fb0, -yb, ZB], [fb0 + w, yb, zB1]],
          [[hb1, -yb, ZB], [xb_back1 + root_len, yb, zB1]],
          [[fb0, -yb, hz_top], [xb_back1 + root_len, yb, zB1]]]
    def boxes(bl, g=0.0):
        return U(*[box(bounds=[np.array(b[0]) - g, np.array(b[1]) + g]) for b in bl])
    ringA, ringB = boxes(bA), boxes(bB)
    c = np.array([(fb0 + xa_far1) / 2, 0, (zAf0 + zA1) / 2])
    from shapely.geometry import box as sbox
    wl = wall_min(rest, sbox(xa_root0, -(hy + w + G), xb_back1 + G, hy + w + G), [ZB + 0.5, zA1, zB1])
    if wl < 1.5: print(f'  AVISO: parede lateral {wl:.1f} mm (<1.5), reduza R')
    A0 = U(I(rest, halfspace(x1=xs)), I(rest, ringA))
    swA = sweep(boxes(bA, G), c)
    pocket = box(bounds=swA.bounds)               # caixa: teto plano (ponte), sem labio pendurado
    B = U(D(I(rest, halfspace(xs + G)), pocket), D(I(rest, ringB), swA))
    A = carve_front(A0, B, c, xa_root0 - 4, xb_back1 + 6)
    print(f'  [elos] emenda x={xs} arame={w:.1f} mm  furo A {xs - ha0 + d2:.1f}x{2 * hy:.1f}  altura {zB1 - ZB:.1f} mm  '
          f'folga ~{play + G:.1f} mm')
    lo = np.minimum(ringA.bounds[0], ringB.bounds[0]) - 0.8; hi = np.maximum(ringA.bounds[1], ringB.bounds[1]) + 0.8
    info = dict(tipo='elos', x=xs, c=c, keep=(xa_root0, xb_back1), protect=box(bounds=[lo, hi]),
                forca=f'arame {w:.1f}x{w:.1f} mm, 2 secoes por elo (preso por geometria, nao solta)')
    return A, B, info


JOINTS = dict(pino=joint_pino, bola=joint_bola, elos=joint_elos)


# ---------------------------------------------------------------- arredondamento
def round_zone(part, xc, r, half=6.0, vox=0.2, protect=None):
    lo, hi = part.bounds
    lo = np.array([max(lo[0], xc - half - 2), lo[1] - 2, lo[2] - 2]); hi = np.array([min(hi[0], xc + half + 2), hi[1] + 2, hi[2] + 2])
    if hi[0] <= lo[0]: return part
    ax = [np.arange(lo[i], hi[i] + vox, vox) for i in range(3)]
    YY, ZZ = np.meshgrid(ax[1], ax[2], indexing='ij'); pts = np.c_[YY.ravel(), ZZ.ravel()]
    ins = np.zeros([len(q) for q in ax], bool)
    for i, x in enumerate(ax[0]):
        sec = part.section(plane_origin=[x, 0, 0], plane_normal=[1, 0, 0])
        if sec is None: continue
        acc = np.zeros(len(pts), int)
        for e in sec.discrete: acc += Path(e[:, 1:3]).contains_points(pts)
        ins[i] = (acc % 2 == 1).reshape(YY.shape)
    er = ndimage.distance_transform_edt(ins) * vox > r
    field = ndimage.distance_transform_edt(~er) * vox - r
    field = ndimage.gaussian_filter(field, 0.4); field[0] = field[-1] = 1.0
    field = np.pad(field, 1, constant_values=1.0)
    v, f, _, _ = measure.marching_cubes(field, 0.0, spacing=(vox,) * 3, allow_degenerate=False)
    om = trimesh.Trimesh(v - vox + lo, f, process=True); om.merge_vertices(); om.fix_normals()
    if om.volume < 0: om.invert()
    if not om.is_volume: om.fill_holes(); om.fix_normals()
    if not om.is_volume:
        print(f'  aviso: arredondamento pulado em x={xc}'); return part
    if protect is not None: om = U(om, protect)
    zone = box(bounds=[[xc - half, -BIG, -BIG], [xc + half, BIG, BIG]])
    return U(D(part, zone), I(I(part, zone), om))      # so tira material, nunca cria


# ---------------------------------------------------------------- checagens
def clean(part):
    """Remove faces degeneradas e lascas (volume ~0) que as booleanas as vezes deixam."""
    part = part.copy()
    part.update_faces(part.nondegenerate_faces(height=1e-7))
    part.remove_unreferenced_vertices()
    bs = part.split(only_watertight=False)
    keep = [b for b in bs if abs(b.volume) > 1.0]
    return trimesh.util.concatenate(keep) if len(keep) != len(bs) and keep else part


def islands(part, layer=0.2, min_area=0.3):
    z0, z1 = part.bounds[:, 2]
    zs = np.arange(z0 + layer / 2, z1, layer)
    secs = part.section_multiplane(plane_origin=[0, 0, 0], plane_normal=[0, 0, 1], heights=zs)
    prev, bad = None, []
    for z, s in zip(zs, secs):
        polys = [p for p in (s.polygons_full if s is not None else []) if p.area > 1e-3]
        if prev is not None:
            for p in polys:
                if p.area > min_area and not p.buffer(0.05).intersects(prev):
                    bad.append((round(float(z), 2), round(p.area, 1)))
        prev = unary_union(polys) if polys else None
    return bad


def seam_gap_top(A, B, x0, x1, ztop):
    """Abertura visivel da emenda no dorso (y=0, 1 mm abaixo do topo) em repouso."""
    z = ztop - 1.0
    o = [[x0 - 20, 0, z]]
    ra = A.ray.intersects_location(o, [[1, 0, 0]])[0]; rb = B.ray.intersects_location(o, [[1, 0, 0]])[0]
    if not len(ra) or not len(rb): return None
    xa = ra[:, 0][ra[:, 0] < x1 + 8].max() if (ra[:, 0] < x1 + 8).any() else None
    xb = rb[:, 0][rb[:, 0] > x0 - 8].min() if (rb[:, 0] > x0 - 8).any() else None
    return None if xa is None or xb is None else xb - xa


def kinematic(Apart, Bpart, c):
    ys = np.linspace(-a.yaw, a.yaw, 9) if a.yaw > 0 else [0]
    ps = np.linspace(-a.pitch_down, a.pitch_up, 7) if a.pitch_up + a.pitch_down > 0 else [0]
    worst = (0.0, 0, 0)
    for y in ys:
        for p in ps:
            x = I(moved(Apart, mrot(c, y, p)), Bpart)
            v = x.volume if len(x.faces) else 0.0
            if v > worst[0]: worst = (v, y, p)
    return worst


# ---------------------------------------------------------------- render
def _ax3d(fig, pos, meshes, el, az, title, lim):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    ax = fig.add_subplot(*pos, projection='3d')
    for i, p in enumerate(meshes):
        q = p.simplify_quadric_decimation(percent=1 - 12000 / len(p.faces), aggression=3) if len(p.faces) > 12000 else p
        n = q.face_normals; shade = 0.55 + 0.45 * np.clip(n @ np.array([0.3, -0.4, 0.85]), 0, 1)
        base = np.array(matplotlib.colors.to_rgb(COLS[i % 4]))
        ax.add_collection3d(Poly3DCollection(q.triangles, facecolors=np.outer(shade, base).clip(0, 1), edgecolor='none'))
    c, r = lim
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(el, az); ax.set_title(title); ax.set_axis_off()


def _sec(ax, meshes, origin, normal, ij, title):
    for i, p in enumerate(meshes):
        s = p.section(plane_origin=origin, plane_normal=normal)
        if s is None: continue
        for e in s.discrete: ax.plot(e[:, ij[0]], e[:, ij[1]], color=COLS[i % 4], lw=0.8)
    ax.set_aspect('equal'); ax.set_title(title, fontsize=9)


def render_parts(parts, infos, ring, path):
    allm = trimesh.util.concatenate(parts); lo, hi = allm.bounds; lim = ((lo + hi) / 2, (hi - lo).max() / 2)
    fig = plt.figure(figsize=(16, 11))
    _ax3d(fig, (3, 3, 1), parts, 25, -60, 'iso', lim)
    _ax3d(fig, (3, 3, 2), parts, 90, -90, 'topo', lim)
    _ax3d(fig, (3, 3, 3), parts, 0, -90, 'lado', lim)
    _sec(fig.add_subplot(3, 3, 4), parts, [0, 0, 0], [0, 1, 0], (0, 2), 'corte lateral y=0')
    for k, inf in enumerate(infos[:2]):
        c = inf['c']
        _sec(fig.add_subplot(3, 3, 5 + k), parts, c, [0, 0, 1], (0, 1), f'junta {k} corte z={c[2]:.1f}')
        ax = fig.add_subplot(3, 3, 7 + k); _sec(ax, parts, c, [1, 0, 0], (1, 2), f'junta {k} corte x={c[0]:.1f}')
    if ring:
        _sec(fig.add_subplot(3, 3, 9), parts, [ring[0], 0, 0], [1, 0, 0], (1, 2), f'tunel x={ring[0]:.1f}')
    plt.tight_layout(); plt.savefig(path, dpi=70); plt.close(fig)


def render_poses(parts, infos, path):
    def pose(y, p):
        ps = [q.copy() for q in parts]
        for j in reversed(range(len(infos))):
            M = mrot(infos[j]['c'], y, p)
            for i in range(j + 1): ps[i].apply_transform(M)
        return ps
    allm = trimesh.util.concatenate(parts); lo, hi = allm.bounds; lim = ((lo + hi) / 2, (hi - lo).max() / 2 + 6)
    fig = plt.figure(figsize=(16, 5))
    _ax3d(fig, (1, 3, 1), pose(a.yaw, 0), 90, -90, f'giro {a.yaw:.0f} graus em cada junta (topo)', lim)
    _ax3d(fig, (1, 3, 2), pose(0, a.pitch_up), 0, -90, f'cabeca sobe {a.pitch_up:.0f} (lado)', lim)
    _ax3d(fig, (1, 3, 3), pose(0, -a.pitch_down), 0, -90, f'cabeca desce {a.pitch_down:.0f} (lado)', lim)
    plt.tight_layout(); plt.savefig(path, dpi=70); plt.close(fig)


# ---------------------------------------------------------------- analyze
def cmd_analyze():
    m = load_model(a)
    lo, hi = m.bounds; Lx = hi[0] - lo[0]
    print(f'tamanho {m.extents.round(1).tolist()} mm  volume {m.volume:.0f} mm3')
    xs = np.arange(lo[0] + 1, hi[0] - 0.5, 1.0)
    hw = np.array([halfwidth(m, x) for x in xs])
    top = np.array([skin_top(m, x) or 0 for x in xs])
    target = 2000 * (Lx / 100) ** 2
    zb = None
    for z in np.arange(lo[2] + 0.2, lo[2] + 4.01, 0.1):
        if sec_area_z(m, z + 0.05) >= target: zb = round(float(z), 1); break
    if zb is None: zb = round(float(lo[2] + 1.5), 1); print(f'  aviso: area de apoio < {target:.0f} mm2 mesmo com 4 mm de corte')
    print(f'base: --zb={zb}  (area ~{sec_area_z(m, zb + 0.05):.0f} mm2, alvo {target:.0f})')
    def argmin_in(f0, f1):
        sel = (xs > lo[0] + f0 * Lx) & (xs < lo[0] + f1 * Lx) & (hw > 0)
        i = np.where(sel)[0][np.argmin(hw[sel])]; return float(xs[i]), float(hw[i])
    cuts = [argmin_in(0.15, 0.42), argmin_in(0.42, 0.72)]
    cutargs = []
    for x, h in cuts:
        zt = top[np.argmin(abs(xs - x))]
        d = min(inscribed(m, x + dx, z) for dx in (-2, 0, 2) for z in (zb + 1, (zb + zt) / 2))
        R = {'pino': d - 0.45 - 1.6, 'bola': d - 0.45 - 1.6, 'elos': (d - 3.3) / 1.5 / 0.55}[a.joint]
        R = round(float(np.clip(R, 2.0, 8.0)), 1)
        cutargs.append(f'--cut={x:.0f}:{R}')
        print(f'corte em x={x:.0f}: meia-largura {h:.1f}, altura {top[np.argmin(abs(xs - x))] - zb:.1f} -> R={R}')
    keep_end = cuts[1][0] + {'pino': 8, 'bola': 12, 'elos': 10}[a.joint]
    ok = (xs > keep_end) & (hw >= 5.5) & (top - 1.4 - 5.1 - zb >= 2.5)
    if ok.any():
        i = max(np.where(ok)[0][0], np.where(ok)[0][-1] - 3)   # perto da traseira, nao na ponta
        rx, rz = float(xs[i]), round(float(top[i] - 1.4), 1)
        ringarg = f'--ring={rx:.0f}:{rz}'
        print(f'tunel: x={rx:.0f} z={rz} (piso {rz - 5.1 - zb:.1f} mm)')
    else:
        ringarg = '--ring=X:Z'; print('  aviso: nao achei lugar automatico p/ o tunel; escolher na mao')
    print('\nSUGESTAO (conferir nas vistas: cabeca em -x? cortes fora de patas/orelhas?):')
    rot = ''.join(f' --rot={r}' for r in (a.rot or [])) + (f' --length={a.length}' if a.length else '')
    print(f'python3 flexi_chaveiro.py build {a.inp} SAIDA.stl --joint={a.joint} --zb={zb} {" ".join(cutargs)} {ringarg}{rot}')
    png = a.png or os.path.splitext(a.inp)[0] + '_analise.png'
    fig = plt.figure(figsize=(15, 9))
    lim = ((lo + hi) / 2, m.extents.max() / 2)
    _ax3d(fig, (2, 3, 1), [m], 25, -60, 'iso', lim); _ax3d(fig, (2, 3, 2), [m], 90, -90, 'topo (cabeca deve estar a esquerda)', lim)
    _ax3d(fig, (2, 3, 3), [m], 0, -90, 'lado', lim)
    ax = fig.add_subplot(2, 1, 2)
    ax.plot(xs, hw, label='meia-largura'); ax.plot(xs, top - zb, label='altura acima da base')
    for x, _ in cuts: ax.axvline(x, color='r', ls='--')
    if ok.any(): ax.axvline(rx, color='k', ls=':')
    ax.legend(); ax.set_xlabel('x (mm)'); ax.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(png, dpi=70); plt.close(fig)
    print('vistas ->', png)


# ---------------------------------------------------------------- build
def cmd_build():
    global ZB
    m = load_model(a)
    ZB = a.zb
    m = I(m, halfspace(z0=ZB))
    print(f'area da base ~{sec_area_z(m, ZB + 0.05):.0f} mm2   modelo {m.extents.round(1).tolist()} mm   junta={a.joint} '
          f'giro +-{a.yaw:.0f} inclina +{a.pitch_up:.0f}/-{a.pitch_down:.0f}')
    cuts = sorted([tuple(map(float, c.split(':'))) for c in a.cut])
    parts, infos, rest = [], [], m
    for xa, R in cuts:
        p, rest, inf = JOINTS[a.joint](rest, xa, R); parts.append(p); infos.append(inf)
    parts.append(rest)
    for (k0, k1), inf in zip([(i['keep']) for i in infos[:-1]], infos[1:]):
        if inf['keep'][0] - k1 < 1.0: print(f'  AVISO: juntas muito perto ({inf["keep"][0] - k1:.1f} mm); afaste os cortes')
    ring = None
    if a.ring:
        rx, rz = map(float, a.ring.split(':')); ring = (rx, rz)
        R_, r_ = a.ring_R, a.ring_r
        t = torus(major_radius=R_, minor_radius=r_, major_sections=96, minor_sections=32)
        t.apply_transform(rotation_matrix(np.pi / 2, [0, 1, 0])); t.apply_translation([rx, 0, rz])
        tgt = [i for i, p in enumerate(parts) if p.contains([[rx, 0, rz - R_]])[0]]
        if not tgt: die('centro do tunel fora do bicho; revise --ring')
        k = tgt[0]
        top = skin_top(parts[k], rx) or rz
        floor = rz - R_ - r_ - ZB; bridge = top - (rz - (R_ - r_))
        dj = min([min(abs(rx - r_ - i['keep'][1]), abs(i['keep'][0] - rx - r_)) for i in infos] or [99])
        print(f'tunel: piso={floor:.1f} ponte={bridge:.1f} distancia da junta={dj:.1f} canal O{2 * r_:.1f}')
        if floor < 2.5: print('  AVISO: piso < 2.5 mm; suba Z do --ring')
        if bridge < 3.5: print('  AVISO: ponte < 3.5 mm; desca Z do --ring')
        if dj < 1.0: print('  AVISO: tunel a < 1 mm da junta; mova X do --ring')
        parts[k] = D(parts[k], t)
    for i, p in enumerate(parts):
        for inf in infos:
            if p.bounds[0, 0] - 6 < inf['x'] < p.bounds[1, 0] + 6:
                p = round_zone(p, inf['x'], a.round, protect=inf['protect'])
        parts[i] = p
    parts = [clean(p) for p in parts]
    ok = True
    print('--- verificacao')
    for i, p in enumerate(parts):
        nb = len(p.split(only_watertight=False))
        isl = islands(p)
        print(f'parte {i}: watertight={p.is_watertight} corpos={nb} vol={p.volume:.0f} ilhas_flutuantes={len(isl)}'
              + (f' {isl[:4]}' if isl else ''))
        ok &= p.is_watertight and nb == 1 and not isl
    for i in range(len(parts) - 1):
        x = I(parts[i], parts[i + 1]); ov = x.volume if len(x.faces) else 0
        v, y, p = kinematic(parts[i], parts[i + 1], infos[i]['c'])
        gap = seam_gap_top(parts[i], parts[i + 1], infos[i]['x'] - 3, infos[i]['x'] + 3,
                           skin_top(m, infos[i]['x']) or 0)
        print(f'junta {i}: sobreposicao={ov:.3f}  pior colisao no movimento={v:.3f} mm3 (giro {y:+.0f}, incl {p:+.0f})'
              f'  emenda no dorso={gap if gap is None else round(gap, 2)} mm')
        print(f'  forca: {infos[i]["forca"]}')
        ok &= ov < 1e-3 and v < 0.5
    base, ext = os.path.splitext(a.out)
    for i, p in enumerate(parts): p.export(f'{base}_parte{i}{ext}')
    allm = trimesh.util.concatenate(parts); allm.export(a.out)
    print(f'filamento (volume solido) {sum(p.volume for p in parts):.0f} mm3')
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        render_parts(parts, infos, ring, os.path.join(a.preview, 'vistas.png'))
        render_poses(parts, infos, os.path.join(a.preview, 'movimento.png'))
        print('preview ->', a.preview)
    print('OK' if ok else 'FALHOU - revisar', '->', a.out)


if __name__ == '__main__':
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    def common(p):
        p.add_argument('inp')
        p.add_argument('--rot', action='append', help='eixo:graus, aplicado antes de tudo (repetivel), ex. z:180')
        p.add_argument('--length', type=float, help='escala o modelo p/ este comprimento em x (mm). Gerar no tamanho final!')
        p.add_argument('--joint', choices=list(JOINTS), default='pino')
    p1 = sub.add_parser('analyze'); common(p1); p1.add_argument('--png')
    p2 = sub.add_parser('build'); common(p2); p2.add_argument('out')
    p2.add_argument('--zb', type=float, required=True)
    p2.add_argument('--cut', action='append', required=True)
    p2.add_argument('--ring')
    p2.add_argument('--gap', type=float, default=0.45)
    p2.add_argument('--yaw', type=float, default=18.0, help='giro horizontal +- graus')
    p2.add_argument('--pitch', type=float, default=12.0, help='inclinacao vertical +- graus (0 = so horizontal)')
    p2.add_argument('--pitch_up', type=float, help='so p/ cima (cabeca sobe); abre a emenda no dorso ~ altura*tan')
    p2.add_argument('--pitch_down', type=float, help='so p/ baixo (cabeca desce); abre a emenda na barriga')
    p2.add_argument('--vang', type=float, default=9.0, help='pino: meio-angulo do V (graus)')
    p2.add_argument('--cap', type=float, default=2.4)
    p2.add_argument('--round', type=float, default=1.0)
    p2.add_argument('--ring_R', type=float, default=3.6)
    p2.add_argument('--ring_r', type=float, default=1.5)
    p2.add_argument('--preview', help='pasta p/ PNGs de verificacao')
    a = ap.parse_args()
    if a.cmd == 'build':
        if os.path.splitext(a.out)[1].lower() != '.stl': die('saida precisa terminar em .stl')
        G = a.gap
        a.pitch_up = a.pitch if a.pitch_up is None else a.pitch_up
        a.pitch_down = a.pitch if a.pitch_down is None else a.pitch_down
        a.pitch = max(a.pitch_up, a.pitch_down)
        cmd_build()
    else:
        a.yaw = a.pitch = a.pitch_up = a.pitch_down = 0
        cmd_analyze()
