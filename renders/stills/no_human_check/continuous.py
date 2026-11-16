import bpy, sys, os, math
S = bpy.data.scenes['Scene']; O = S.objects
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc8_restaged') == 1 and not S.get('tc9_continuous')
def bag(idb):
    ad = idb.animation_data
    for layer in ad.action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(ad.action_slot)
            if cb: return cb
def curve(idb, path, idx=0):
    return next((c for c in bag(idb).fcurves if c.data_path == path and c.array_index == idx), None)
def ss(a, b, f):
    t = min(1.0, max(0.0, (f - a) / float(b - a))); return t * t * (3 - 2 * t)
def pchip(xs, ys):
    n = len(xs); h = [xs[i + 1] - xs[i] for i in range(n - 1)]; d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]; m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    def ev(x):
        if x <= xs[0]: return ys[0]
        if x >= xs[-1]: return ys[-1]
        i = max(j for j in range(n - 1) if xs[j] <= x); t = (x - xs[i]) / h[i]
        return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * m[i] + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * m[i + 1])
    return ev
def rewrite(idb, path, idx, a, b, fn):
    """replace all keys in [a,b] by one linear key per frame; neighbours outside keep their values"""
    c = curve(idb, path, idx)
    pre = c.evaluate(a - 1) if a > 1 else None; post = c.evaluate(b + 1) if b < 7200 else None
    for k in reversed([k for k in c.keyframe_points if a - 1 <= k.co.x <= b + 1]): c.keyframe_points.remove(k, fast=True)
    def put(f, v, interp):
        k = c.keyframe_points.insert(f, v, options={'FAST'}); k.interpolation = interp
    if pre is not None: put(a - 1, pre, 'CONSTANT')
    for f in range(a, b + 1): put(f, fn(f), 'LINEAR')
    if post is not None: put(b + 1, post, 'LINEAR')
    c.update()
def fresh(idb, path, n, frames, fn):
    cb = bag(idb)
    for c in [c for c in cb.fcurves if c.data_path == path]: cb.fcurves.remove(c)
    for i in range(n):
        c = cb.fcurves.new(path, index=i)
        for f in frames:
            k = c.keyframe_points.insert(f, fn(f)[i], options={'FAST'}); k.interpolation = 'LINEAR'
        c.update()
A0, A1, B0, B1 = 1, 1200, 6241, 7200
WIDE_B = ((6.965, -21.312, 2.811), (0.201, 4.051, 4.333))
P = (0.7, -1.2, 0.093)
# frame: (camera, target, lens, fstop)
KA = {1: ((4.6, -15.0, 1.9), (0.5, 3.0, 1.65), 32, 8), 120: ((4.45, -14.4, 1.88), (0.5, 2.8, 1.6), 32, 8),
      300: ((1.5, -2.7, 0.95), (0.72, -1.15, 0.12), 48, 8), 430: ((1.75, -2.96, 1.2), (0.82, -0.95, 0.22), 50, 8),
      560: ((2.5, -4.55, 1.3), (0.87, -0.5, 0.3), 45, 8), 700: ((3.1, -5.4, 1.48), (1.05, -0.35, 0.4), 45, 8),
      990: ((3.6, -6.0, 1.6), (1.27, -0.3, 0.6), 45, 8), 1090: ((3.75, -6.4, 1.65), (1.3, -0.3, 0.7), 44, 8),
      1200: ((4.0, -13.0, 1.8), (0.5, 3.0, 1.65), 32, 8)}
KB = {6241: (WIDE_B[0], WIDE_B[1], 32, 8), 6290: ((6.8, -20.6, 2.78), (0.22, 3.9, 4.2), 32, 8),
      6420: ((3.394, -5.872, 1.55), (1.131, -0.215, 0.63), 45, 8), 6600: ((3.25, -5.5, 1.5), (1.0, -0.45, 0.45), 45, 8),
      6700: ((2.6, -3.7, 1.32), (0.85, -0.9, 0.32), 40, 8), 6790: ((1.33, -2.6, 0.88), (0.709, -1.187, 0.221), 50, 8),
      6880: ((1.29, -2.47, 0.88), (0.728, -1.18, 0.195), 50, 8),
      6950: ((P[0] + 0.10, P[1] - 0.40, P[2] + 0.62), P, 60, 5.6), 6990: ((P[0] + 0.06, P[1] - 0.30, P[2] + 0.48), P, 60, 5.6),
      7040: ((1.7, -4.2, 1.15), (0.62, -0.7, 0.45), 45, 8),
      7135: (WIDE_B[0], WIDE_B[1], 32, 8), 7200: (WIDE_B[0], WIDE_B[1], 32, 8)}
cam = O['TC_Camera']; tgt = O['TC_CamTarget']; foc = O['TC_Focus']
for K, a, b in ((KA, A0, A1), (KB, B0, B1)):
    xs = sorted(K)
    for i in range(3):
        rewrite(cam, 'location', i, a, b, pchip(xs, [K[x][0][i] for x in xs]))
        e = pchip(xs, [K[x][1][i] for x in xs])
        rewrite(tgt, 'location', i, a, b, e); rewrite(foc, 'location', i, a, b, e)
    rewrite(cam.data, 'lens', 0, a, b, pchip(xs, [K[x][2] for x in xs]))
    rewrite(cam.data, 'dof.aperture_fstop', 0, a, b, pchip(xs, [K[x][3] for x in xs]))
    for p in ('shift_x', 'shift_y'):
        c = curve(cam.data, p)
        if c and any(abs(k.co.y) > 1e-6 for k in c.keyframe_points if a <= k.co.x <= b): rewrite(cam.data, p, 0, a, b, lambda f: 0.0)
for o, cn in ((tgt, 'TC Story Photo Aim'), (foc, 'TC Story Photo Focus')):
    cb = bag(o)
    for c in [c for c in cb.fcurves if 'influence' in c.data_path]: cb.fcurves.remove(c)
    o.constraints[cn].influence = 0.0
# no cuts inside the two sequences any more -> motion blur stays on
sh = curve(S, 'render.motion_blur_shutter')
for k in reversed([k for k in sh.keyframe_points if 3 <= k.co.x <= A1 or B0 + 2 <= k.co.x <= B1]): sh.keyframe_points.remove(k, fast=True)
sh.update()
print('SHUTTER keys', [(int(k.co.x), round(k.co.y, 2)) for k in sh.keyframe_points if k.co.x < 1300 or k.co.x > 6200])
# props move by themselves
BESIDE, INPIT, UP = (0.7, -1.2, 0.005), (0.9, -0.6, -0.443), 0.335
def cap(f):
    if f < 3000:
        t1, t2, t3 = ss(450, 500, f), ss(495, 600, f), ss(595, 690, f)
        return (BESIDE[0] + (INPIT[0] - BESIDE[0]) * t2, BESIDE[1] + (INPIT[1] - BESIDE[1]) * t2, BESIDE[2] + (UP - BESIDE[2]) * t1 + (INPIT[2] - UP) * t3)
    u1, u2, u3 = ss(6590, 6665, f), ss(6660, 6735, f), ss(6730, 6775, f)
    return (INPIT[0] + (BESIDE[0] - INPIT[0]) * u2, INPIT[1] + (BESIDE[1] - INPIT[1]) * u2, INPIT[2] + (UP - INPIT[2]) * u1 + (BESIDE[2] - UP) * u3)
fresh(O['TC_Capsule'], 'location', 3, [1] + list(range(449, 692)) + list(range(6589, 6777)) + [7200], cap)
def hinge(f):
    return ((-1.745 * (1 - ss(360, 425, f)) if f < 3000 else -1.833 * ss(6795, 6865, f)), 0.0, 0.0)
fresh(O['TC_Capsule_Hinge'], 'rotation_euler', 3, [1] + list(range(359, 427)) + list(range(6794, 6867)) + [7200], hinge)
def stone(f):
    t = ss(1000, 1060, f)
    return (1.76 + (1.4 - 1.76) * t, -0.95 + (-1.25 + 0.95) * t, 0.105 + 0.24 * math.sin(math.pi * t))
fresh(O['TC_Marker_Stone'], 'location', 3, [1] + list(range(999, 1062)) + [7200], stone)
# grass grows a little over the years, on top of the seasonal keys
def setkeys(o, keys):
    if not o.animation_data: o.animation_data_create()
    if not o.animation_data.action:
        o.scale = (1, 1, keys[0][1]); o.keyframe_insert('scale', index=2, frame=keys[0][0])
    c = curve(o, 'scale', 2)
    for k in reversed(list(c.keyframe_points)): c.keyframe_points.remove(k, fast=True)
    for f, v in keys:
        k = c.keyframe_points.insert(f, v, options={'FAST'}); k.interpolation = 'BEZIER'; k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
    c.update()
setkeys(O['TC_Grass_Base'], [(1, 0.8), (1273, 0.8), (1921, 1.0), (2641, 1.0), (3481, 0.7), (4561, 1.15), (6240, 1.25), (7200, 1.3)])
setkeys(O['TC_Grass_Lush'], [(1, 0.45), (1273, 0.45), (1921, 1.0), (2641, 0.9), (3481, 0.15), (4081, 0.25), (4561, 1.0), (4800, 1.1), (7200, 1.25)])
for n in ('TC5_Rooted_Varied_Tussocks', 'TC4_Bent_Foreground_Grass'):
    setkeys(O[n], [(1, 0.8), (1273, 0.8), (2400, 1.0), (3481, 0.85), (4800, 1.25), (7200, 1.35)])
S['tc9_continuous'] = 1
print('CONTINUOUS APPLIED actions', len(bpy.data.actions), flush=True)
if '--render' in args:
    outdir = args[args.index('--render') + 1]; os.makedirs(outdir, exist_ok=True)
    if '--full' not in args:
        S.render.resolution_x, S.render.resolution_y = 480, 270; S.eevee.taa_render_samples = 8; S.render.use_motion_blur = False
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 88
    for part in args[args.index('--render') + 2].split(','):
        a, b, st = [int(x) for x in part.split(':')]
        for f in range(a, b + 1, st):
            S.frame_set(f); S.render.filepath = os.path.join(outdir, 'p_%04d.jpg' % f)
            bpy.ops.render.render(write_still=True, scene='Scene')
    print('RENDERED', flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1
    bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, flush=True)
