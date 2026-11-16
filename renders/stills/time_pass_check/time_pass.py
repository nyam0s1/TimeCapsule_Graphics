"""TC13 pass: real-looking pit, opaque envelope, day/night cycle, year counter, weather-driven grass.
Run on the saved TimeCapsule.blend:  blender -b TimeCapsule.blend --python time_pass.py -- [--render DIR FRAMES RESX SAMPLES] [--anim FILE START END STEP RESX SAMPLES] [--save]
Guard: scene property tc13_time_pass.  Needs tc13_year_atlas.png next to this script (it is packed into the file)."""
import bpy, bmesh, sys, os, math, random, time
import numpy as np
from mathutils import Vector, Matrix, noise
HERE = os.path.dirname(os.path.abspath(__file__))
S = bpy.data.scenes['Scene']; O = S.objects; M = bpy.data.materials
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc12_look_pass') == 1 and not S.get('tc13_time_pass')

F0, F1 = 1201, 6240                 # the time-lapse
YEAR0, DAWNS = 2001, 25             # burial year, number of sunrises in the time-lapse (one sunrise = one year)
SUNUP = 0.82                        # share of a cycle with the sun above the horizon
NOON = SUNUP / 2
P = (F1 - F0) / (DAWNS - 1 + NOON + (1 - 0.855))   # cycle length in frames: starts in the night, ends at noon
def phase(f): return NOON + (f - F1) / P
def sst(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))); return t * t * (3 - 2 * t)
# ---- solar model -------------------------------------------------------------------------------------------
# Sun position from spherical astronomy, sunlight from Beer-Lambert extinction along the Kasten-Young air mass,
# skylight from the clear-sky diffuse illuminance law with an exponential twilight. Site: 32 deg S, north = -Y, east = -X.
LAT = math.radians(-32.0)
# time-lapse dwell: screen time per unit of hour angle. Nights pass 4 times faster, sunrise and sunset are held 2.6 times longer.
_H = np.linspace(-math.pi, math.pi, 4001); _a = np.abs(_H)
_g = (1.0 - 0.75 * np.clip((_a - 1.75) / 0.35, 0, 1) ** 2 * (3 - 2 * np.clip((_a - 1.75) / 0.35, 0, 1))) * (1 + 1.6 * np.exp(-((_a - math.pi / 2) / 0.22) ** 2))
_T = np.concatenate([[0.0], np.cumsum((_g[1:] + _g[:-1]) / 2)]); _T /= _T[-1]          # share of the cycle elapsed at hour angle H, noon at 0.5
SUNRISE = float(np.interp(-math.pi / 2, _H, _T)) - 0.5 + NOON                      # phase of the equinox sunrise
TAU = (0.180, 0.230, 0.361)         # vertical optical depth R,G,B: Rayleigh 0.008735 L^-4.08 + aerosol 0.06 L^-1.3 (L = 0.61, 0.55, 0.465 um)
ADAPT = 0.80                        # exposure adaptation: the camera follows part of the brightness range (power law)
FLOOR = 0.06                       # moonlit night sky after adaptation
def hour_angle(f):
    return float(np.interp((phase(f) - NOON + 0.5) % 1.0, _T, _H))
def airmass(h):                     # Kasten & Young 1989, h = apparent altitude in radians
    hd = max(math.degrees(h), -0.9); return 1.0 / (math.sin(math.radians(hd)) + 0.50572 * (hd + 6.07995) ** -1.6364)
def transmit(h): return [math.exp(-t * airmass(h)) for t in TAU]
def lum(c): return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def skylight(h):                    # clear-sky diffuse horizontal illuminance, klx: 0.8 + 15.5 sqrt(sin h); twilight falls tenfold per 3 degrees
    return 0.8 + 15.5 * math.sqrt(math.sin(h)) if h > 0 else 0.8 * 10 ** (math.degrees(h) / 3.0)
SOL = {}
def solar(f, zen_noon):
    """zen_noon: the art-directed midday sun angle of that era; it fixes the season (declination) of the cycle"""
    dec = max(-0.409, min(0.409, zen_noon + LAT)); H = hour_angle(f)
    sh = math.sin(LAT) * math.sin(dec) + math.cos(LAT) * math.cos(dec) * math.cos(H); h = math.asin(sh)
    east = -math.cos(dec) * math.sin(H); north = math.sin(dec) * math.cos(LAT) - math.cos(dec) * math.cos(H) * math.sin(LAT)
    hn = math.pi / 2 - (dec - LAT)                                   # altitude at local noon
    rel = [a / b for a, b in zip(transmit(h), transmit(hn))]
    disc = sst(math.radians(-0.27), math.radians(0.27), h)           # share of the solar disc above the horizon
    L = lum(rel)
    return dict(h=h, dir=Vector((-east, -north, sh)), energy=(L * disc) ** ADAPT, tint=[c / L for c in rel],
                sky=FLOOR + (1 - FLOOR) * (skylight(h) / skylight(hn)) ** ADAPT, tw=math.exp(-(math.degrees(h) / 5.0) ** 2))
def sky_day(f): return SOL[f]['sky'] if F0 <= f <= F1 else 1.0
def twilight(f): return SOL[f]['tw'] if F0 <= f <= F1 else 0.0

# ---------- helpers ----------
def fcurves(idb):
    ad = idb.animation_data
    if not ad or not ad.action: return []
    out = []
    for layer in ad.action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                if ad.action_slot is None or cb.slot_handle == ad.action_slot.handle: out += list(cb.fcurves)
    return out
def fcu(idb, path, idx=0):
    return next((f for f in fcurves(idb) if f.data_path == path and f.array_index == idx), None)
def rekey(idb, path, keys, idx=-1, interp='BEZIER'):
    """replace all keys of a property by the given (frame, value) list"""
    for f in [f for f in fcurves(idb) if f.data_path == path and (idx < 0 or f.array_index == idx)]:
        for layer in idb.animation_data.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    if f in list(cb.fcurves): cb.fcurves.remove(f); break
    for fr, v in keys:
        if path.startswith('['): idb[path[2:-2]] = v
        elif idx >= 0:
            a = list(getattr(idb, path)); a[idx] = v; setattr(idb, path, a)
        else: setattr(idb, path, v)
        idb.keyframe_insert(path, index=idx, frame=fr)
    for f in fcurves(idb):
        if f.data_path == path and (idx < 0 or f.array_index == idx):
            for k in f.keyframe_points: k.interpolation = interp
            f.update()
def bake(idb, path, idx, fn):
    """per-frame keys over the time-lapse: fn(frame, original value) -> new value; keys outside stay as they are"""
    f = fcu(idb, path, idx); assert f, (idb.name, path, idx)
    orig = [f.evaluate(fr) for fr in range(F0, F1 + 1)]; after = f.evaluate(F1 + 1)
    for i, fr in enumerate(range(F0, F1 + 1)):
        k = f.keyframe_points.insert(fr, fn(fr, orig[i]), options={'FAST'}); k.interpolation = 'LINEAR'
    f.keyframe_points.insert(F1 + 1, after, options={'FAST'})         # the reopening keeps its own keyed light from its first frame
    f.update()
def scene_driver(idb, path, expr, props, idx=-1):
    fc = idb.driver_add(path, idx) if idx >= 0 else idb.driver_add(path)
    d = fc.driver; d.type = 'SCRIPTED'
    for name, prop in props.items():
        v = d.variables.new(); v.name = name; v.type = 'SINGLE_PROP'; t = v.targets[0]; t.id_type = 'SCENE'; t.id = S
        t.data_path = prop if prop.startswith('render') else '["%s"]' % prop
    d.expression = expr
    return fc
def value_node(nt, name, expr, props):
    n = nt.nodes.new('ShaderNodeValue'); n.name = n.label = name
    scene_driver(nt, 'nodes["%s"].outputs[0].default_value' % name, expr, props)
    return n
def math_node(nt, op, a=None, b=None, c=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    for i, x in enumerate((a, b, c)):
        if x is None: continue
        if isinstance(x, (int, float)): n.inputs[i].default_value = x
        else: nt.links.new(x, n.inputs[i])
    return n.outputs[0]
def mix_node(nt, blend, fac, c1, c2):
    n = nt.nodes.new('ShaderNodeMixRGB'); n.blend_type = blend
    for sock, x in zip(n.inputs, (fac, c1, c2)):
        if isinstance(x, (int, float)): sock.default_value = x
        elif isinstance(x, tuple): sock.default_value = (*x, 1.0) if len(x) == 3 else x
        else: nt.links.new(x, sock)
    return n.outputs[0]
def noise_node(nt, vec, scale, detail=2.0, rough=0.5):
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    nt.links.new(vec, n.inputs['Vector']); return n.outputs[0]

# =====================================================================================
# 1. THE PIT
# =====================================================================================
pit = O['TC_Hole_Pit']; old = pit.data
rim = [pit.matrix_world @ old.vertices[i].co for i in range(16)]
cx, cy = 0.9, -0.6; ZB = -0.445; SEG = 6; NR = 26; NF = 7
ring0 = []
for i in range(16):
    a, b = rim[i], rim[(i + 1) % 16]
    for s in range(SEG): ring0.append(a.lerp(b, s / SEG))
NP = len(ring0)
def nz(p, sc, seed=0.0): return noise.noise(Vector((p.x * sc + seed, p.y * sc - seed, p.z * sc + 2 * seed)))
bm = bmesh.new(); rings = []
for k in range(NR + 1):
    t = k / NR; row = []
    for j, r in enumerate(ring0):
        inward = Vector((cx - r.x, cy - r.y, 0)).normalized()
        z = r.z + (ZB - r.z) * t
        p = Vector((r.x, r.y, z))
        w = sst(0.0, 0.10, t)                                        # the rim itself stays welded to the ground opening
        lip = 0.014 * sst(0.0, 0.07, t)                              # crumbled, rounded edge
        ledge = 0.010 * sst(0.16, 0.22, t)                           # the harder subsoil stands a little proud of the topsoil cut
        fillet = 0.035 * max(0.0, (t - 0.84) / 0.16) ** 2            # loose soil gathered at the foot of the wall
        rough = w * (0.013 * nz(p, 9.0) + 0.007 * nz(p, 27.0, 3.1) + 0.006 * nz(Vector((p.x, p.y, p.z * 0.15)), 40.0, 7.7))   # last term: vertical spade cuts
        row.append(bm.verts.new(p + inward * (lip + ledge + fillet + rough)))
    rings.append(row)
for m in range(1, NF + 1):                                           # floor
    s = 1 - m / NF; row = []
    for v in rings[NR]:
        p = Vector((cx + (v.co.x - cx) * s, cy + (v.co.y - cy) * s, 0)); p.z = ZB + 0.012 * nz(p, 11.0, 5.0) + 0.006 * nz(p, 37.0, 1.3) + 0.01 * (1 - s) ** 2
        row.append(bm.verts.new(p))
        if m == NF: break
    rings.append(row)
for k in range(len(rings) - 1):
    A, B = rings[k], rings[k + 1]
    for j in range(NP):
        if len(B) == 1: bm.faces.new((A[j], A[(j + 1) % NP], B[0]))
        else: bm.faces.new((A[j], A[(j + 1) % NP], B[(j + 1) % NP], B[j]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.faces.ensure_lookup_table()
if bm.faces[-1].normal.z < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces)
for f in bm.faces: f.smooth = True
new = bpy.data.meshes.new('TC13_Hole_Pit'); bm.to_mesh(new); bm.free()
old.name = 'TC_Hole_Pit_before_TC13'; old.use_fake_user = True
pit.data = new

pm = bpy.data.materials.new('TC13_Pit_Soil'); pm.use_nodes = True; nt = pm.node_tree; N = nt.nodes; L = nt.links
bsdf = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
tc = N.new('ShaderNodeTexCoord'); co = tc.outputs['Object']
sep = N.new('ShaderNodeSeparateXYZ'); L.new(co, sep.inputs[0])
depth = math_node(nt, 'MULTIPLY_ADD', sep.outputs['Z'], -1 / 0.47, 0.03 / 0.47, clamp=True)          # 0 at the surface, 1 at the bottom
warp = math_node(nt, 'MULTIPLY_ADD', noise_node(nt, co, 6.0, 3.0), 0.10, -0.05)
ramp = N.new('ShaderNodeValToRGB'); L.new(math_node(nt, 'ADD', depth, warp, clamp=True), ramp.inputs[0])
cr = ramp.color_ramp; stops = [(0.0, (0.21, 0.145, 0.085)), (0.05, (0.065, 0.043, 0.026)), (0.21, (0.075, 0.049, 0.029)), (0.29, (0.23, 0.135, 0.066)),
                               (0.66, (0.20, 0.118, 0.060)), (0.84, (0.115, 0.077, 0.047)), (1.0, (0.095, 0.066, 0.042))]
cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1); cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
for pos, col in stops[1:-1]:
    e = cr.elements.new(pos); e.color = (*col, 1)
mott = math_node(nt, 'MULTIPLY_ADD', noise_node(nt, co, 34.0, 4.0, 0.6), 0.75, 0.62)                    # clumps of lighter and darker soil
col = mix_node(nt, 'MULTIPLY', 1.0, ramp.outputs[0], mott)
peb_n = noise_node(nt, co, 26.0, 1.0)
peb = math_node(nt, 'MULTIPLY', math_node(nt, 'SUBTRACT', peb_n, 0.69), 14.0, clamp=True)               # sparse small stones in the wall
col = mix_node(nt, 'MIX', peb, col, (0.34, 0.31, 0.27))
occ = math_node(nt, 'MULTIPLY_ADD', math_node(nt, 'POWER', depth, 0.8), -0.68, 1.0)                     # little sky reaches the bottom of a narrow pit
col = mix_node(nt, 'MULTIPLY', 1.0, col, occ)
L.new(col, bsdf.inputs['Base Color'])
L.new(math_node(nt, 'MULTIPLY_ADD', depth, -0.22, 0.97), bsdf.inputs['Roughness'])                      # damper, slightly glossier soil deeper down
mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 0.12); L.new(co, mp.inputs['Vector'])
b1 = N.new('ShaderNodeBump'); b1.inputs['Strength'].default_value = 0.9; b1.inputs['Distance'].default_value = 0.02; L.new(noise_node(nt, mp.outputs[0], 38.0, 2.0), b1.inputs['Height'])
b2 = N.new('ShaderNodeBump'); b2.inputs['Strength'].default_value = 0.8; b2.inputs['Distance'].default_value = 0.012; L.new(noise_node(nt, co, 20.0, 3.0), b2.inputs['Height']); L.new(b1.outputs[0], b2.inputs['Normal'])
b3 = N.new('ShaderNodeBump'); b3.inputs['Strength'].default_value = 0.5; b3.inputs['Distance'].default_value = 0.003; L.new(noise_node(nt, co, 120.0, 2.0, 0.65), b3.inputs['Height']); L.new(b2.outputs[0], b3.inputs['Normal'])
b4 = N.new('ShaderNodeBump'); b4.inputs['Strength'].default_value = 1.0; b4.inputs['Distance'].default_value = 0.006; L.new(peb, b4.inputs['Height']); L.new(b3.outputs[0], b4.inputs['Normal'])
L.new(b4.outputs[0], bsdf.inputs['Normal'])
new.materials.append(pm)

# loose crumbs of dug soil round the opening
src = O['TC5_Deposited_Soil_01_00'].data
sv = np.array([v.co[:] for v in src.vertices]); sv = (sv - sv.mean(0)) / np.abs(sv - sv.mean(0)).max()
sf = [tuple(p.vertices) for p in src.polygons]
rnd = random.Random(13); cv = []; cf = []
for i in range(150):
    j = rnd.randrange(NP); r = ring0[j]; out = Vector((r.x - cx, r.y - cy, 0)).normalized()
    dist = 0.006 + 0.13 * rnd.random() ** 2.2; size = rnd.uniform(0.006, 0.018) * (1.25 - dist / 0.14)
    pos = Vector((r.x, r.y, r.z)) + out * dist + Vector((rnd.uniform(-.02, .02), rnd.uniform(-.02, .02), size * 0.25 - cy * 0))
    pos.z = r.z + size * 0.22 - 0.002
    R = (Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'X')).to_3x3()
    sc = Vector((size * rnd.uniform(0.8, 1.3), size * rnd.uniform(0.8, 1.3), size * rnd.uniform(0.55, 0.9)))
    base = len(cv)
    for v in sv:
        q = R @ Vector(v); cv.append((pos.x - cx + q.x * sc.x, pos.y - cy + q.y * sc.y, pos.z + q.z * sc.z))
    cf += [tuple(base + a for a in f) for f in sf]
cme = bpy.data.meshes.new('TC13_Pit_Rim_Crumbs'); cme.from_pydata(cv, [], cf); cme.update()
for p in cme.polygons: p.use_smooth = True
cme.materials.append(M['TC_Dug_Soil'])
crumbs = bpy.data.objects.new('TC13_Pit_Rim_Crumbs', cme); crumbs.location = (cx, cy, 0)
for c in pit.users_collection: c.objects.link(crumbs)
for fr, z in ((1, 0.0), (962, 0.0), (990, -0.045), (6440, -0.045), (6565, 0.0), (7200, 0.0)):      # trodden in while filling, back when the pit is dug out
    crumbs.location.z = z; crumbs.keyframe_insert('location', index=2, frame=fr)
for fr, h in ((1, False), (991, True), (6440, False)):
    crumbs.hide_render = crumbs.hide_viewport = h; crumbs.keyframe_insert('hide_render', frame=fr); crumbs.keyframe_insert('hide_viewport', frame=fr)

# =====================================================================================
# 2. CAPSULE FLOOR: the envelope was 35 % transparent, which EEVEE renders as dither grain ("TV static")
# =====================================================================================
next(n for n in M['TC_Envelope'].node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled').inputs['Alpha'].default_value = 1.0

# =====================================================================================
# 3. DAY AND NIGHT in the time-lapse
# =====================================================================================
sun = O['TC_Sun']; assert sun.rotation_mode == 'XYZ'
fx = fcu(sun, 'rotation_euler', 0)
for fr in range(F0, F1 + 1): SOL[fr] = solar(fr, min(0.96, max(0.15, fx.evaluate(fr))))
for prop, fn in (('tc_day', sky_day), ('tc_twilight', twilight)):
    S[prop] = fn(1); S.keyframe_insert('["%s"]' % prop, frame=1)
    f = fcu(S, '["%s"]' % prop)
    for fr in list(range(F0, F1 + 1)) + [F0 - 1, F1 + 1, 7200]:
        k = f.keyframe_points.insert(fr, fn(fr), options={'FAST'}); k.interpolation = 'LINEAR'
    f.keyframe_points[0].interpolation = 'LINEAR'; f.update()
bake(sun.data, 'energy', 0, lambda fr, v: v * SOL[fr]['energy'])
for i in range(3):
    bake(sun.data, 'color', i, lambda fr, v, i=i: v * SOL[fr]['tint'][i])
prev = None; EUL = {}
for fr in range(F0, F1 + 1):                                         # the lamp shines along -dir
    q = (-SOL[fr]['dir']).to_track_quat('-Z', 'Y'); prev = q.to_euler('XYZ', prev) if prev is not None else q.to_euler('XYZ'); EUL[fr] = prev.copy()
for i in range(3):
    bake(sun, 'rotation_euler', i, lambda fr, v, i=i: EUL[fr][i])
moon_d = bpy.data.lights.new('TC13_Moon', 'SUN'); moon_d.color = (0.55, 0.68, 1.0); moon_d.angle = 0.03; moon_d.energy = 0.0
moon_d.use_shadow_jitter = True
moon = bpy.data.objects.new('TC13_Moon', moon_d); moon.location = (5, -6, 9); moon.rotation_euler = (0.80, 0.0, 2.35)
for c in sun.users_collection: c.objects.link(moon)
scene_driver(moon_d, 'energy', '1.3*(1-d)**2', {'d': 'tc_day'})
for n in ('TC_Polish_SkyFill', 'TC_Story_Ground_Bounce_Fill'):                    # the fill lights follow the sky strength, which has no night
    d = O[n].data.animation_data.drivers[0].driver
    v = d.variables.new(); v.name = 'tcd'; v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'SCENE'; v.targets[0].id = S; v.targets[0].data_path = '["tc_day"]'
    d.expression = '(%s)*(0.14+0.86*tcd)' % d.expression
W = S.world.node_tree; WN = W.nodes; WL = W.links
sky = WN['TC_Sky']; frm = sky.inputs['Color'].links[0].from_socket; WL.remove(sky.inputs['Color'].links[0])
tint = WN.new('ShaderNodeRGB'); tint.name = tint.label = 'TC13 Day Night Tint'
NIGHT = (0.06, 0.09, 0.19)
for i in range(3):
    scene_driver(W, 'nodes["TC13 Day Night Tint"].outputs[0].default_value', '(d*(1-(1-d)**4)+%g*(1-d)**4)*(1-tw*%g)' % (NIGHT[i], (0.0, 0.16, 0.32)[i]), {'d': 'tc_day', 'tw': 'tc_twilight'}, idx=i)
dn = mix_node(W, 'MULTIPLY', 1.0, frm, tint.outputs[0]); dn.node.name = 'TC13 Day Night'
wtc = WN.new('ShaderNodeTexCoord')
vor = WN.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 34.0; WL.new(wtc.outputs['Generated'], vor.inputs['Vector'])
vsep = WN.new('ShaderNodeSeparateColor'); WL.new(vor.outputs['Color'], vsep.inputs[0])
star = math_node(W, 'MULTIPLY', math_node(W, 'SUBTRACT', 0.045, vor.outputs['Distance']), 45.0, clamp=True)       # one small dot per cell...
star = math_node(W, 'MULTIPLY', star, math_node(W, 'MULTIPLY', math_node(W, 'SUBTRACT', vsep.outputs[0], 0.74), 3.0, clamp=True))   # ...in under half of the cells, at varied brightness
gain = value_node(W, 'TC13 Star Gain', '1.3*(1-d)**3*(1-min(1,max(0,1.7*r+0.35*w)))', {'d': 'tc_day', 'r': 'tc_rain', 'w': 'tc_wetness'})
stars = math_node(W, 'MULTIPLY', star, gain.outputs[0])
comb = WN.new('ShaderNodeCombineXYZ')
for i in range(3): WL.new(stars, comb.inputs[i])
WL.new(mix_node(W, 'ADD', 1.0, dn, comb.outputs[0]), sky.inputs['Color'])
for m in M:                                                                        # distance haze is an emission; it must not glow at night
    if not m.node_tree: continue
    hz = m.node_tree.nodes.get('Story Distant Atmospheric Perspective')
    if not hz: continue
    for sock in hz.inputs:
        if sock.is_linked and sock.links[0].from_node.bl_idname == 'ShaderNodeEmission':
            em = sock.links[0].from_node; st = em.inputs['Strength']
            if st.is_linked: print('HAZE linked strength, skipped', m.name); continue
            scene_driver(m.node_tree, 'nodes["%s"].inputs[%d].default_value' % (em.name, list(em.inputs).index(st)), '%g*(0.03+0.97*d)' % st.default_value, {'d': 'tc_day'})
g = next(n for n in M['TC_New_Glass'].node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')     # the rebuilt school has lit windows at night
g.inputs['Emission Color'].default_value = (1.0, 0.66, 0.30, 1.0)
scene_driver(M['TC_New_Glass'].node_tree, 'nodes["%s"].inputs[%d].default_value' % (g.name, list(g.inputs).index(g.inputs['Emission Strength'])), '1.1*max(0,1-2.5*d)', {'d': 'tc_day'})

# =====================================================================================
# 4. YEAR COUNTER (compositor overlay, bottom right; one sunrise = one year)
# =====================================================================================
keys = [(1, 0.0)]; yr = 0
for fr in range(F0, F1 + 1):
    if math.floor(phase(fr) - SUNRISE) > math.floor(phase(fr - 1) - SUNRISE): yr += 1; keys.append((fr, float(yr)))
assert yr == DAWNS, yr
S['tc_year'] = 0.0; rekey(S, '["tc_year"]', keys, interp='CONSTANT')
S['tc_year_first'] = YEAR0
img = bpy.data.images.load(os.path.join(HERE, 'tc13_year_atlas.png')); img.name = 'tc13_year_atlas.png'; img.pack(); img.filepath = '//textures/tc13_year_atlas.png'
RW, RH = 224, 80
cg = bpy.data.node_groups.new('TC13 Year Counter', 'CompositorNodeTree'); CN = cg.nodes; CL = cg.links
cg.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = CN.new('CompositorNodeRLayers'); rl.scene = S
im = CN.new('CompositorNodeImage'); im.image = img
crop = CN.new('CompositorNodeCrop'); crop.name = 'TC13 Year Row'; CL.new(im.outputs['Image'], crop.inputs['Image'])
crop.inputs['X'].default_value = 0; crop.inputs['Width'].default_value = RW; crop.inputs['Height'].default_value = RH
scene_driver(cg, 'nodes["TC13 Year Row"].inputs[2].default_value', 'int(round(y))*%d' % RH, {'y': 'tc_year'})
tr = CN.new('CompositorNodeTransform'); tr.name = 'TC13 Year Place'; CL.new(crop.outputs['Image'], tr.inputs['Image'])
rp = {'rx': 'render.resolution_x', 'ry': 'render.resolution_y', 'pc': 'render.resolution_percentage'}
scene_driver(cg, 'nodes["TC13 Year Place"].inputs[1].default_value', '(rx/2-rx/1920*%d)*pc/100' % (44 + RW // 2), rp)
scene_driver(cg, 'nodes["TC13 Year Place"].inputs[2].default_value', '-(ry/2-rx/1920*%d)*pc/100' % (34 + RH // 2), rp)
scene_driver(cg, 'nodes["TC13 Year Place"].inputs[4].default_value', 'rx/1920*pc/100', rp)
ao = CN.new('CompositorNodeAlphaOver'); CL.new(rl.outputs['Image'], ao.inputs['Background']); CL.new(tr.outputs['Image'], ao.inputs['Foreground'])
go = CN.new('NodeGroupOutput'); CL.new(ao.outputs['Image'], go.inputs[0])
S.compositing_node_group = cg; S.render.use_compositing = True

# =====================================================================================
# 5. GRASS: yellow under the harsh sun, green and dense in the rain
# =====================================================================================
rekey(S, '["tc_grass_dry"]', [(1, 0.35), (1200, 0.35), (1320, 0.3), (1700, 0.0), (2400, 0.0), (2700, 0.35), (3200, 1.0), (3600, 1.0), (4800, 0.92), (4900, 0.85), (5350, 0.0), (6240, 0.0), (7200, 0.06)])
S['tc_grass_lush'] = 0.0
rekey(S, '["tc_grass_lush"]', [(1, 0.2), (1273, 0.2), (1921, 1.0), (2500, 1.0), (3300, 0.55), (4800, 0.55), (5400, 1.0), (6240, 1.0), (7200, 1.0)])
rekey(O['TC_Grass_Base'], 'scale', [(1, 0.8), (1273, 0.8), (1921, 1.08), (2641, 1.0), (3300, 0.85), (4800, 0.85), (5400, 1.2), (6240, 1.28), (7200, 1.3)], idx=2)
rekey(O['TC_Grass_Lush'], 'scale', [(1, 0.45), (1273, 0.45), (1921, 1.08), (2500, 1.0), (3300, 0.6), (4800, 0.6), (5400, 1.1), (6240, 1.2), (7200, 1.25)], idx=2)
for n in ('TC5_Rooted_Varied_Tussocks', 'TC4_Bent_Foreground_Grass'):
    rekey(O[n], 'scale', [(1, 0.8), (1273, 0.8), (2400, 1.05), (3300, 0.8), (4800, 0.8), (5400, 1.25), (7200, 1.35)], idx=2)
# colours
gn = M['TC_Grass'].node_tree.nodes
for e, c in zip(gn['Color Ramp'].color_ramp.elements, ((0.055, 0.21, 0.025), (0.17, 0.42, 0.06))): e.color = (*c, 1)
for e, c in zip(gn['Color Ramp.001'].color_ramp.elements, ((0.46, 0.36, 0.11), (0.76, 0.63, 0.25))): e.color = (*c, 1)
gn['Mix (Legacy)'].inputs['Color2'].default_value = (0.92, 0.96, 0.88, 1); gn['Mix (Legacy).001'].inputs['Color2'].default_value = (0.95, 0.94, 0.88, 1)
for i, k in enumerate((1.0, 0.82, 1.2)):
    mx = M['TC5_Grass_Tone_%d' % i].node_tree.nodes['Mix (Legacy)']
    mx.inputs['Color1'].default_value = (0.085 * k, 0.27 * k, 0.04 * k, 1); mx.inputs['Color2'].default_value = (0.58 * k, 0.47 * k, 0.17 * k, 1)
mx = M['Story Field Grass'].node_tree.nodes['Mix (Legacy)']
mx.inputs['Color1'].default_value = (0.06, 0.19, 0.03, 1); mx.inputs['Color2'].default_value = (0.50, 0.41, 0.15, 1)
# two more layers of blades that only come up in wet years
def world_xy(o):
    n = len(o.data.vertices); a = np.empty(n * 3); o.data.vertices.foreach_get('co', a); a = a.reshape(n, 3)
    mw = np.array(o.matrix_world); return (a @ mw[:3, :3].T + mw[:3, 3])[:, :2]
lush = O['TC_Grass_Lush']
for tag, off in (('A', (0.13, 0.09)), ('B', (-0.11, 0.14))):
    o = lush.copy(); o.data = lush.data.copy(); o.name = 'TC13_Rain_Grass_' + tag; o.data.name = o.name
    o.animation_data_clear(); o.scale = (1, 1, 1)
    for c in lush.users_collection: c.objects.link(o)
    o.location = (lush.location.x + off[0], lush.location.y + off[1], lush.location.z)
    b = bmesh.new(); b.from_mesh(o.data)
    lx, ly = cx - o.location.x, cy - o.location.y      # no blades hanging over the pit, the capsule spot or the mound
    dead = [v for v in b.verts if (abs(v.co.x - lx) < 0.62 and abs(v.co.y - ly) < 0.62) or (abs(v.co.x - (0.7 - o.location.x)) < 0.3 and abs(v.co.y - (-1.2 - o.location.y)) < 0.3)]
    doomed = set()
    for v in dead:
        for f in v.link_faces: doomed.update(f.verts)
    bmesh.ops.delete(b, geom=list(doomed), context='VERTS'); b.to_mesh(o.data); b.free()
    mat = M['TC_Grass'].copy(); mat.name = 'TC13_Grass_Rain_' + tag; o.data.materials[0] = mat
    mod = o.modifiers[0]; ng = mod.node_group.copy(); ng.name = 'TC13_Rooted_' + o.name; mod.node_group = ng
    for d in ng.animation_data.drivers: d.driver.variables[0].targets[0].id = o
    rekey(o, 'scale', [(1, 0.03), (1300, 0.03), (1921, 1.05 if tag == 'A' else 0.9), (2500, 1.0), (3250, 0.03), (4860, 0.03), (5400, 1.15 if tag == 'A' else 1.0), (6240, 1.25), (7200, 1.3)], idx=2)
    for fr, h in ((1, True), (1300, False), (3251, True), (4860, False)):
        o.hide_render = o.hide_viewport = h; o.keyframe_insert('hide_render', frame=fr); o.keyframe_insert('hide_viewport', frame=fr)
# the soil under the blades takes the colour of the sward: per-vertex cover from the real blade positions
def cover(ground, grasses, cell):
    pts = np.concatenate([world_xy(o) for o in grasses]); gxy = world_xy(ground)
    lo = gxy.min(0) - cell; hi = gxy.max(0) + cell; shape = np.ceil((hi - lo) / cell).astype(int) + 1
    ij = np.floor((pts - lo) / cell).astype(int); ok = (ij >= 0).all(1) & (ij < shape).all(1)
    H = np.zeros(shape); np.add.at(H, (ij[ok, 0], ij[ok, 1]), 1.0)
    for _ in range(2):
        Hp = np.pad(H, 1, mode='edge'); H = sum(Hp[1 + a:1 + a + shape[0], 1 + b:1 + b + shape[1]] for a in (-1, 0, 1) for b in (-1, 0, 1)) / 9
    ref = np.percentile(H[H > 0], 80) if (H > 0).any() else 1.0
    gi = np.clip(np.floor((gxy - lo) / cell).astype(int), 0, shape - 1)
    val = np.clip(H[gi[:, 0], gi[:, 1]] / ref, 0, 1)
    val[(np.abs(gxy[:, 0] - cx) < 0.75) & (np.abs(gxy[:, 1] - cy) < 0.75)] = 0          # keep the worked earth bare
    at = ground.data.attributes.new('TC13_Grass_Cover', 'FLOAT', 'POINT'); at.data.foreach_set('value', val.astype(np.float32))
    print('COVER', ground.name, 'mean', round(float(val.mean()), 3), flush=True)
cover(O['TC_Ground'], [O['TC_Grass_Base'], O['TC_Grass_Lush'], O['TC5_Rooted_Varied_Tussocks']], 0.3)
cover(O['Story Distant Rolling Terrain'], [O['Story Rooted Outer Field Grass']], 2.0)
nt = M['TC_Ground'].node_tree; N = nt.nodes; L = nt.links
at = N.new('ShaderNodeAttribute'); at.attribute_name = 'TC13_Grass_Cover'; at.name = 'TC13 Grass Cover'
tcg = N.new('ShaderNodeTexCoord')
dry = value_node(nt, 'TC13 Grass Dry', 'v', {'v': 'tc_grass_dry'}); lsh = value_node(nt, 'TC13 Grass Lush', 'v', {'v': 'tc_grass_lush'})
patch = math_node(nt, 'MULTIPLY_ADD', noise_node(nt, tcg.outputs['Object'], 2.3, 4.0, 0.6), 1.7, -0.35, clamp=True)
fine = math_node(nt, 'MULTIPLY_ADD', noise_node(nt, tcg.outputs['Object'], 60.0, 2.0, 0.7), 0.9, 0.55)
amount = math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', at.outputs['Fac'], patch), math_node(nt, 'MULTIPLY_ADD', lsh.outputs[0], 0.62, 0.16), clamp=True)
sward = mix_node(nt, 'MIX', dry.outputs[0], (0.075, 0.19, 0.035), (0.40, 0.32, 0.13))
sward = mix_node(nt, 'MULTIPLY', 1.0, sward, fine)
for b in [n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled']:
    sock = b.inputs['Base Color']
    if not sock.is_linked: continue
    src_s = sock.links[0].from_socket; L.remove(sock.links[0]); L.new(mix_node(nt, 'MIX', amount, src_s, sward), sock)

S['tc13_time_pass'] = 1
import json
json.dump({str(f): [round(math.degrees(v['h']), 2), round(v['energy'], 4), round(v['sky'], 4), [round(c, 3) for c in v['tint']]] for f, v in SOL.items()}, open(os.path.join(HERE, 'solar_curve.json'), 'w'))
print('TC13 APPLIED  cycle %.1f frames, year keys %s' % (P, [k[0] for k in keys]), flush=True)

# ---------- output ----------
def lowres(resx, samples):
    S.render.resolution_x = resx; S.render.resolution_y = resx * 9 // 16; S.render.resolution_percentage = 100
    S.eevee.taa_render_samples = samples; S.render.use_motion_blur = False
if '--render' in args:
    i = args.index('--render'); outdir = args[i + 1]; os.makedirs(outdir, exist_ok=True); lowres(int(args[i + 3]), int(args[i + 4]))
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 90
    for f in [int(x) for x in args[i + 2].split(',')]:
        t = time.time(); S.frame_set(f); S.render.filepath = os.path.join(outdir, 'tp_%04d.jpg' % f); bpy.ops.render.render(write_still=True, scene='Scene')
        print('FRAME', f, round(time.time() - t, 1), flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1
    bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
