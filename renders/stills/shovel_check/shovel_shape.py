"""TC14: round-point digging shovel. New blade and socket meshes for TC_Shovel (new) and TC11_OldShovel (aged).
blender -b TimeCapsule.blend --python shovel_shape.py -- [--closeups DIR] [--save]     Guard: scene property tc14_shovel_shape."""
import bpy, bmesh, sys, os, math, random
from mathutils import Vector
S = bpy.data.scenes['Scene']; O = S.objects
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc13_time_pass') == 1 and not S.get('tc14_shovel_shape')
# Local frame of the shovel: Z along the shaft (tip down), X across the blade, the working face looks toward -Y.
ROWS = [  # z, half width, dish depth
    (0.125, 0.100, 0.022), (0.098, 0.105, 0.024), (0.040, 0.104, 0.023), (-0.020, 0.099, 0.021),
    (-0.070, 0.084, 0.017), (-0.110, 0.060, 0.012), (-0.140, 0.032, 0.006), (-0.158, 0.009, 0.002)]
NU = 10
def blade_point(z, w, d, u, top=0.0):
    a = abs(u)
    yc = 0.009 - (0.016 * ((0.04 - z) / 0.2) ** 2 if z < 0.04 else 0.0)          # the point sweeps slightly forward
    return Vector((u * w, yc - d * a ** 2.2, z - top * a ** 1.5))                 # edges stand forward of the centre: a scoop
def build_blade(name, wear=0.0, seed=0):
    rnd = random.Random(seed); bm = bmesh.new(); grid = []
    for r, (z, w, d) in enumerate(ROWS):
        row = []
        for i in range(NU + 1):
            u = -1 + 2 * i / NU
            p = blade_point(z, w, d, u, top=(0.024, 0.008)[r] if r < 2 else 0.0)  # shoulders slope down from the socket
            if wear and (r >= len(ROWS) - 3 or abs(u) > 0.99):                    # worn, slightly bent cutting edge
                p += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * wear
            row.append(bm.verts.new(p))
        grid.append(row)
    for r in range(len(ROWS) - 1):
        for i in range(NU):
            bm.faces.new((grid[r][i], grid[r + 1][i], grid[r + 1][i + 1], grid[r][i + 1]))
    z, w, d = ROWS[0]
    for sgn in (-1, 1):                                                          # turned-over foot treads on the shoulders
        us = [sgn * x for x in (0.36, 0.58, 0.80, 0.98)]
        a = [bm.verts.new(blade_point(z, w, d, u, top=0.024) + Vector((0, -0.0005, 0.0005))) for u in us]
        b = [bm.verts.new(blade_point(z, w, d, u, top=0.024) + Vector((0, -0.015, 0.004))) for u in us]
        for k in range(3): bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces: f.smooth = True
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); return me
def build_socket(name, old):
    """tapered socket that runs out into a ridge down the blade (the frog); the two rivets are kept from the old mesh"""
    bm = bmesh.new(); SEG = 16
    prof = [(0.266, 0.0168, 0.0), (0.2685, 0.0200, 0.0), (0.268, 0.0228, 0.0), (0.262, 0.0228, 0.0),   # rolled collar closing on the shaft
            (0.258, 0.0212, 0.0), (0.200, 0.0206, 0.0), (0.135, 0.0190, 0.001),
            (0.095, 0.0150, 0.003), (0.055, 0.0100, 0.0055), (0.020, 0.0050, 0.0075), (-0.005, 0.0015, 0.0085)]
    rings = [[bm.verts.new((r * math.cos(2 * math.pi * k / SEG), yc + r * math.sin(2 * math.pi * k / SEG), z)) for k in range(SEG)] for z, r, yc in prof]
    for a, b in zip(rings, rings[1:]):
        for k in range(SEG): bm.faces.new((a[k], a[(k + 1) % SEG], b[(k + 1) % SEG], b[k]))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces: f.smooth = True
    keep = {}
    for p in old.polygons:                                                       # rivets: every old face that does not touch the old tube
        if min(p.vertices) >= 24:
            vs = []
            for i in p.vertices:
                if i not in keep: keep[i] = bm.verts.new(old.vertices[i].co)
                vs.append(keep[i])
            try: bm.faces.new(vs)
            except ValueError: pass
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); return me
def swap(obj_name, me):
    o = O[obj_name]; old = o.data; mats = list(old.materials)
    for m in mats: me.materials.append(m)
    old.name = old.name + '_before_TC14'; old.use_fake_user = True; o.data = me
old_socket = O['TC4_Shovel_Ferrule_And_Rivets'].data
swap('TC_Shovel_Blade', build_blade('TC14_Shovel_Blade'))
swap('TC4_Shovel_Ferrule_And_Rivets', build_socket('TC14_Shovel_Socket', old_socket))
swap('TC11_OldShovel_Blade', build_blade('TC14_OldShovel_Blade', wear=0.0035, seed=11))
swap('TC11_OldShovel_Ferrule', build_socket('TC14_OldShovel_Socket', old_socket))
S['tc14_shovel_shape'] = 1
print('TC14 APPLIED', flush=True)
if '--closeups' in args:
    out = args[args.index('--closeups') + 1]; os.makedirs(out, exist_ok=True)
    cd = bpy.data.cameras.new('tmp'); cam = bpy.data.objects.new('tmp', cd); S.collection.objects.link(cam); film = S.camera; cd.lens = 70; cd.dof.use_dof = False
    S.render.resolution_x = 800; S.render.resolution_y = 600; S.eevee.taa_render_samples = 24; S.render.use_motion_blur = False; S.render.image_settings.file_format = 'JPEG'
    comp = S.compositing_node_group
    def shot(f, target, tag, views, own=True):
        S.frame_set(f); S.camera = cam if own else film; S.compositing_node_group = None if own else comp
        c = O[target].matrix_world.translation.copy()
        for i, (off, look) in enumerate(views):
            if own:
                cam.location = c + Vector(off); cam.rotation_euler = ((c + Vector(look)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
            S.render.filepath = os.path.join(out, '%s_%d.jpg' % (tag, i)); bpy.ops.render.render(write_still=True, scene='Scene')
    for a in args[args.index('--closeups') + 2:]:
        f = int(a)
        if f > 0: shot(f, 'TC_Shovel' if (f < 1200 or f > 6240) else 'TC11_OldShovel', 'close_%04d' % f, [((0.25, -1.0, 0.45), (0, 0, 0.05)), ((-0.8, 0.7, 0.5), (0, 0, 0.05)), ((0.9, 0.3, 0.25), (0, 0, 0.05))])
        else: shot(-f, 'TC_Shovel', 'film_%04d' % -f, [((0, 0, 0), (0, 0, 0))], own=False)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1; bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
