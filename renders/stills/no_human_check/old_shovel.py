import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix, Euler, Quaternion
S = bpy.data.scenes['Scene']; O = S.objects
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc10_shovel_works') == 1 and not S.get('tc11_old_shovel')
S.frame_set(1199)
sh = O['TC_Shovel']; coll = sh.users_collection[0]
PL = Vector((1.9, -0.4, 0.06)); PQ = Euler((0, -0.13, 0.2)).to_quaternion()
assert (sh.matrix_world.translation - PL).length < 1e-3
ZB = 0.55                                   # break height along the shaft (root space)
def empty(name, parent=None):
    e = bpy.data.objects.new(name, None); e.empty_display_size = 0.1; coll.objects.link(e); e.parent = parent; e.rotation_mode = 'QUATERNION'; return e
root = empty('TC11_OldShovel'); top = empty('TC11_OldShovel_Top', root); top.location = (0, 0, ZB)
Tinv = Matrix.Translation((0, 0, -ZB))
inv = sh.matrix_world.inverted()
# ---- ageing materials ----
S['tc_shovel_age'] = 0.0
for f, v in ((1, 0.0), (1200, 0.0), (2400, 0.45), (3600, 0.75), (4800, 0.9), (6240, 1.0), (7200, 1.0)):
    S['tc_shovel_age'] = v; S.keyframe_insert('["tc_shovel_age"]', frame=f)
def aged(src, name, tones, rough, scale, gain):
    m = bpy.data.materials[src].copy(); m.name = name; nt = m.node_tree; N = nt.nodes; L = nt.links
    p = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    age = N.new('ShaderNodeValue'); age.name = age.label = 'TC11 Age'
    d = nt.driver_add('nodes["TC11 Age"].outputs[0].default_value').driver; d.type = 'SUM'
    v = d.variables.new(); v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'SCENE'; v.targets[0].id = S; v.targets[0].data_path = '["tc_shovel_age"]'
    tc = N.new('ShaderNodeTexCoord')
    n1 = N.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = scale; n1.inputs['Detail'].default_value = 6.0; L.new(tc.outputs['Object'], n1.inputs['Vector'])
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = scale * 5; L.new(tc.outputs['Object'], n2.inputs['Vector'])
    thr = N.new('ShaderNodeMath'); thr.operation = 'MULTIPLY_ADD'; L.new(age.outputs[0], thr.inputs[0]); thr.inputs[1].default_value = -gain; thr.inputs[2].default_value = 1.0
    sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; L.new(n1.outputs[0], sub.inputs[0]); L.new(thr.outputs[0], sub.inputs[1])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.use_clamp = True; L.new(sub.outputs[0], mul.inputs[0]); mul.inputs[1].default_value = 5.0
    tone = N.new('ShaderNodeMixRGB'); tone.inputs['Color1'].default_value = (*tones[0], 1); tone.inputs['Color2'].default_value = (*tones[1], 1); L.new(n2.outputs[0], tone.inputs['Fac'])
    def over(sock, target):
        mx = N.new('ShaderNodeMixRGB'); L.new(mul.outputs[0], mx.inputs['Fac'])
        if sock.is_linked:
            frm = sock.links[0].from_socket; L.remove(sock.links[0]); L.new(frm, mx.inputs['Color1'])
        else:
            dv = sock.default_value; mx.inputs['Color1'].default_value = tuple(dv) if hasattr(dv, '__len__') else (dv, dv, dv, 1)
        if isinstance(target, float): mx.inputs['Color2'].default_value = (target, target, target, 1)
        else: L.new(target, mx.inputs['Color2'])
        L.new(mx.outputs[0], sock)
    over(p.inputs['Base Color'], tone.outputs[0]); over(p.inputs['Roughness'], rough); over(p.inputs['Metallic'], 0.0)
    return m
MATS = {'TC_Shovel_Blade': aged('TC_Shovel_Blade', 'TC11_Old_Blade_Rust', ((0.075, 0.03, 0.014), (0.19, 0.075, 0.03)), 0.92, 9.0, 1.3),
        'TC_Shovel_Wood': aged('TC_Shovel_Wood', 'TC11_Old_Wood_Grey', ((0.15, 0.135, 0.12), (0.27, 0.25, 0.22)), 0.96, 14.0, 1.25),
        'TC4_Tool_Grip': aged('TC4_Tool_Grip', 'TC11_Old_Grip_Faded', ((0.13, 0.11, 0.09), (0.22, 0.19, 0.16)), 0.95, 20.0, 1.3)}
# ---- pieces ----
pieces = []
def piece(src, name, parent, basis):
    o = src.copy(); o.data = src.data.copy(); o.name = name; o.animation_data_clear(); coll.objects.link(o) if o.name not in coll.objects else None
    o.parent = parent; o.matrix_parent_inverse = Matrix.Identity(4); o.matrix_basis = basis
    for sl in o.material_slots:
        if sl.material and sl.material.name in MATS: sl.material = MATS[sl.material.name]
    pieces.append(o); return o
def cut(o, M, keep_upper):
    """bisect the shaft copy with a slanted plane at ZB (root space) and close the break"""
    Mi = M.inverted(); co = Mi @ Vector((0, 0, ZB)); no = (Mi.to_3x3() @ Vector((0.35, 0.1, 1.0))).normalized()
    bm = bmesh.new(); bm.from_mesh(o.data)
    r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, clear_inner=keep_upper, clear_outer=not keep_upper)
    edges = [e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    if edges: bmesh.ops.triangle_fill(bm, edges=edges, use_beauty=True)
    bm.to_mesh(o.data); bm.free()
for c in sh.children:
    M = inv @ c.matrix_world
    if c.name == 'TC_Shovel_Blade': piece(c, 'TC11_OldShovel_Blade', root, M)
    elif c.name == 'TC4_Shovel_Ferrule_And_Rivets': piece(c, 'TC11_OldShovel_Ferrule', root, M)
    elif c.name == 'TC_Shovel_Grip': piece(c, 'TC11_OldShovel_Grip', top, Tinv @ M)
    elif c.name == 'TC_Shovel_Shaft':
        cut(piece(c, 'TC11_OldShovel_Shaft_Lower', root, M), M, False)
        cut(piece(c, 'TC11_OldShovel_Shaft_Upper', top, Tinv @ M), M, True)
assert len(pieces) == 5, [p.name for p in pieces]
for o in pieces:
    for path in ('hide_render', 'hide_viewport'):
        setattr(o, path, True); o.keyframe_insert(path, frame=1); setattr(o, path, False); o.keyframe_insert(path, frame=1200)
    ad = o.animation_data
    for layer in ad.action.layers:
        for strip in layer.strips:
            for c in strip.channelbag(ad.action_slot).fcurves:
                for k in c.keyframe_points: k.interpolation = 'CONSTANT'
# ---- years of leaning, then it falls and snaps in the storm (lightning at 5401) ----
LEAN = Euler((0.10, -0.30, 0.2)).to_quaternion()
LYING = (Matrix.Rotation(0.25, 3, 'Z') @ Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))).to_quaternion()   # shaft along +X, blade flat
LL = Vector((2.18, -0.34, 0.05)); F0, F1 = 5396, 5412
def keyroot(f, loc, q, prev=[None]):
    if prev[0] is not None and q.dot(prev[0]) < 0: q = -q
    prev[0] = q.copy(); root.location = loc; root.rotation_quaternion = q
    root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_quaternion', frame=f)
keyroot(1, PL, PQ); keyroot(1200, PL, PQ); keyroot(3600, PL, PQ.slerp(LEAN, 0.6)); keyroot(F0 - 1, PL, LEAN)
for f in range(F0, F1 + 1):
    t = (f - F0) / float(F1 - F0); e = t * t
    keyroot(f, PL.lerp(LL, e) + Vector((0, 0, 0.05 * math.sin(math.pi * t))), LEAN.slerp(LYING, e))
for f, z in ((F1 + 2, 0.022), (F1 + 4, 0.0)):       # tiny bounce
    keyroot(f, LL + Vector((0, 0, z)), LYING)
keyroot(7200, LL, LYING)
def keytop(f, loc, q):
    top.location = loc; top.rotation_quaternion = q; top.keyframe_insert('location', frame=f); top.keyframe_insert('rotation_quaternion', frame=f)
Q0 = Quaternion((1, 0, 0, 0)); QK = Quaternion((0, 1, 0), 0.42)
keytop(1, (0, 0, ZB), Q0); keytop(F1 - 1, (0, 0, ZB), Q0); keytop(F1 + 4, (0.03, 0, ZB + 0.06), QK); keytop(7200, (0.03, 0, ZB + 0.06), QK)
for e in (root, top):
    ad = e.animation_data
    for layer in ad.action.layers:
        for strip in layer.strips:
            for c in strip.channelbag(ad.action_slot).fcurves:
                for k in c.keyframe_points: k.interpolation = 'LINEAR'
S['tc11_old_shovel'] = 1
print('OLD SHOVEL BUILT pieces', [p.name for p in pieces], 'actions', len(bpy.data.actions), flush=True)
if '--render' in args:
    outdir = args[args.index('--render') + 1]; os.makedirs(outdir, exist_ok=True)
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 90
    S.render.resolution_x, S.render.resolution_y = 960, 540; S.eevee.taa_render_samples = 16
    def shot(f, tag):
        S.frame_set(f); S.render.filepath = os.path.join(outdir, 'p_%04d%s.jpg' % (f, tag)); bpy.ops.render.render(write_still=True, scene='Scene')
    for f in [int(x) for x in args[args.index('--render') + 2].split(',')]: shot(f, '')
    # debug close-ups (never saved): camera parked next to the shovel
    cam = O['TC_Camera']; tg = O['TC_CamTarget']; fo = O['TC_Focus']
    for o in (cam, tg, fo): o.animation_data.action = None
    cam.data.animation_data.action = None; cam.data.lens = 35; cam.data.dof.aperture_fstop = 11; cam.data.shift_x = cam.data.shift_y = 0
    for f in [int(x) for x in args[args.index('--render') + 3].split(',')]:
        cam.location = (3.3, -2.6, 1.0); tg.location = fo.location = (2.2, -0.4, 0.4); shot(f, '_closeup')
    print('RENDERED', flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1
    bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, flush=True)
