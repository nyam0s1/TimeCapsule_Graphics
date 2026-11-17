"""TC17: lightning stays in the clouds (no whole-frame camera flash); background trees lose branches in the dry
season and regrow them in the wet season.
blender -b TimeCapsule.blend --python storm_branches.py -- [--apply] [--render DIR FRAMES RESX SAMPLES] [--save]
Without --apply the script only renders (used for 'before' stills).   Guard: tc17_storm_branches."""
import bpy, sys, os, math, time
import numpy as np
from mathutils import Vector
S = bpy.data.scenes['Scene']; O = S.objects
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

def fcurves(idb):
    ad = idb.animation_data; out = []
    if ad and ad.action:
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    if ad.action_slot is None or cb.slot_handle == ad.action_slot.handle: out += list(cb.fcurves)
    return out
def key_prop(name, pairs, interp='LINEAR'):
    S[name] = float(pairs[0][1]); S.keyframe_insert('["%s"]' % name, frame=pairs[0][0])
    fc = next(f for f in fcurves(S) if f.data_path == '["%s"]' % name)
    for fr, v in pairs[1:]: fc.keyframe_points.insert(fr, v, options={'FAST'})
    for k in fc.keyframe_points: k.interpolation = interp
    fc.update()
def drive(idb, path, expr, props, idx=-1):
    fc = idb.driver_add(path, idx) if idx >= 0 else idb.driver_add(path); d = fc.driver; d.type = 'SCRIPTED'
    for n, p in props.items():
        v = d.variables.new(); v.name = n; v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'SCENE'; v.targets[0].id = S; v.targets[0].data_path = '["%s"]' % p
    d.expression = expr

def apply():
    assert S.get('tc16_cloud_flow') == 1 and not S.get('tc17_storm_branches')
    # ---------------- 1. lightning ----------------
    # The lightning lamp was a sun at energy 35 (the daylight sun is about 0.23 during the storm), so every strike
    # lit the whole frame about 150x: a camera flash. Keep only a faint flicker on the ground (peak 0.05) and put
    # the visible flash in the clouds, in the direction the camera is looking.
    L = O['TC_Lightning']; fc = next(f for f in fcurves(L.data) if f.data_path == 'energy')
    peak = max(k.co[1] for k in fc.keyframe_points)
    strikes = []
    for k in fc.keyframe_points:
        if k.co[1] == peak and (not strikes or k.co[0] - strikes[-1] > 4): strikes.append(int(k.co[0]))
        k.co[1] *= 0.05 / peak; k.handle_left[1] *= 0.05 / peak; k.handle_right[1] *= 0.05 / peak
    fc.update()
    L.data.angle = 0.6                                            # broad, shadow-soft sky light rather than a hard strobe
    pulse = (1.0, 0.17, 0.8, 0.25, 0.0)                           # the lamp's own triple-flicker shape, plus a short fade
    fl = [(1, 0.0)]; az = [(1, 0.0)]; rng = np.random.default_rng(17)
    for s in strikes:
        fl += [(s - 1, 0.0)] + [(s + i, v) for i, v in enumerate(pulse)]
        S.frame_set(s); cam = S.camera.matrix_world; fwd = -Vector(cam.col[2][:3]); a = math.atan2(fwd.y, fwd.x) + rng.uniform(-0.45, 0.45)
        az += [(s - 1, a)]
    key_prop('tc_cloud_flash', fl); key_prop('tc_flash_az', az, 'CONSTANT')
    W = S.world.node_tree; WN = W.nodes; WL = W.links
    # The sky's own strength was also keyed up about 7x on each strike (0.35 -> 2.5), lighting the whole frame
    # through the world light. Hold it at the level just before each strike.
    sfc = next(f for f in fcurves(W) if f.data_path == 'nodes["TC_Sky"].inputs[1].default_value')
    flat = 0
    for s in strikes:
        base = sfc.evaluate(s - 1)
        for k in sfc.keyframe_points:
            if s <= k.co[0] <= s + 4 and abs(k.co[1] - base) > 1e-4:
                k.co[1] = base; k.handle_left[1] = base; k.handle_right[1] = base; flat += 1
    sfc.update(); print('SKY STRENGTH KEYS FLATTENED', flat, [round(sfc.evaluate(s), 3) for s in strikes], flush=True)
    tc = WN.new('ShaderNodeTexCoord'); dn = WN.new('ShaderNodeCombineXYZ'); dn.name = 'TC17 Flash Direction'
    EL = 0.20                                                    # about 11 degrees above the horizon: low storm cells
    for i, (ax, e) in enumerate((('X', 'cos(a)*%r' % math.cos(EL)), ('Y', 'sin(a)*%r' % math.cos(EL)))):
        drive(W, 'nodes["TC17 Flash Direction"].inputs[%d].default_value' % i, e, {'a': 'tc_flash_az'})
    dn.inputs['Z'].default_value = math.sin(EL)
    nv = WN.new('ShaderNodeVectorMath'); nv.operation = 'NORMALIZE'; WL.new(tc.outputs['Generated'], nv.inputs[0])
    dt = WN.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'; WL.new(nv.outputs[0], dt.inputs[0]); WL.new(dn.outputs[0], dt.inputs[1])
    def m(op, a, b=None, clamp=False):
        n = WN.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: WL.new(x, n.inputs[i])
        return n.outputs[0]
    lobe = m('POWER', m('MAXIMUM', dt.outputs['Value'], 0.0), 18.0)                 # cell about 20 degrees across
    halo = m('MULTIPLY', m('POWER', m('MAXIMUM', dt.outputs['Value'], 0.0), 3.0), 0.12)  # faint wide glow through the cloud deck
    sz = WN.new('ShaderNodeSeparateXYZ'); WL.new(nv.outputs[0], sz.inputs[0])
    above = m('MULTIPLY', m('SUBTRACT', sz.outputs['Z'], 0.0), 12.0, clamp=True)      # nothing below the horizon
    sky = WN['Story Weather Skies']; bw = WN.new('ShaderNodeRGBToBW'); WL.new(sky.outputs[0], bw.inputs[0])
    cloud = m('POWER', m('MINIMUM', bw.outputs[0], 1.0), 1.5)                      # light comes out of the clouds, not the gaps
    fv = WN.new('ShaderNodeValue'); fv.name = fv.label = 'TC17 Cloud Flash'; drive(W, 'nodes["TC17 Cloud Flash"].outputs[0].default_value', 'f', {'f': 'tc_cloud_flash'})
    amt = m('MULTIPLY', m('MULTIPLY', m('ADD', lobe, halo), m('MULTIPLY', above, cloud)), m('MULTIPLY', fv.outputs[0], 2.2))
    final = WN['Mix (Legacy)']; bg = WN['TC_Sky']
    add = WN.new('ShaderNodeMixRGB'); add.name = 'TC17 Add Cloud Flash'; add.blend_type = 'ADD'; add.use_clamp = False
    WL.new(amt, add.inputs['Fac']); WL.new(final.outputs[0], add.inputs['Color1']); add.inputs['Color2'].default_value = (0.78, 0.84, 1.0, 1)
    WL.new(add.outputs[0], bg.inputs['Color'])

    # ---------------- 2. background tree branches ----------------
    # Per mesh, every branch segment (an island of the trunk mesh) and every leaf (an island of the leaf mesh) gets
    # a sector (which limb it belongs to), its reach from the crown centre (0..1), and a pivot (its inner end).
    # A geometry-nodes group retracts each limb from its tip inward when the seasonal loss passes that limb's own
    # threshold, and grows it back out when the loss falls again; leaves on a retracted limb go with it.
    NSEC = 7
    def islands(me):
        n = len(me.vertices); parent = list(range(n))
        def find(a):
            while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for e in me.edges:
            a, b = find(e.vertices[0]), find(e.vertices[1])
            if a != b: parent[a] = b
        roots = np.array([find(i) for i in range(n)]); _, inv = np.unique(roots, return_inverse=True); return inv
    def co(me):
        a = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', a); return a.reshape(-1, 3)
    def put(me, name, typ, vals):
        if name in me.attributes: me.attributes.remove(me.attributes[name])
        at = me.attributes.new(name, typ, 'POINT'); at.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value', vals.ravel())
    for i in range(5):
        tm = bpy.data.meshes['TCP_Distant_Trunk_%d' % i]; lm = bpy.data.meshes['TCP_Distant_Leaves_%d' % i]
        tc_, lc = co(tm), co(lm); ti, li = islands(tm), islands(lm)
        tcen = np.array([tc_[ti == k].mean(0) for k in range(ti.max() + 1)])
        main = np.hypot(tcen[:, 0], tcen[:, 1]) < 0.045                                 # the main stem stays
        z0 = min(tc_[ti == k][:, 2].min() for k in range(len(tcen)) if not main[k])      # where the first limb leaves the stem
        ctr = np.array([0, 0, z0])
        rmax = np.linalg.norm(lc - ctr, axis=1).max()
        off = (i * 0.37) % (2 * math.pi / NSEC)
        def sector(p): return np.floor(((np.arctan2(p[..., 1], p[..., 0]) + off) % (2 * math.pi)) / (2 * math.pi / NSEC))
        piv = np.zeros_like(tc_); rin = np.zeros(len(tc_)); rout = np.zeros(len(tc_)); sec = np.zeros(len(tc_))
        for k in range(len(tcen)):
            sel = ti == k; p = tc_[sel]; r = np.linalg.norm(p - ctr, axis=1) / rmax
            if main[k]: piv[sel] = p.mean(0); continue                                 # rin = rout = 0: never retracts
            piv[sel] = p[np.argmin(r)]; rin[sel] = r.min(); rout[sel] = r.max(); sec[sel] = sector(tcen[k])
        put(tm, 'tc17_pivot', 'FLOAT_VECTOR', piv); put(tm, 'tc17_rin', 'FLOAT', rin); put(tm, 'tc17_rout', 'FLOAT', rout); put(tm, 'tc17_sector', 'FLOAT', sec)
        lpiv = np.zeros_like(lc); lrin = np.zeros(len(lc)); lrout = np.zeros(len(lc)); lsec = np.zeros(len(lc))
        for k in range(li.max() + 1):
            sel = li == k; c = lc[sel].mean(0); r = np.linalg.norm(c - ctr) / rmax
            lpiv[sel] = c; lrin[sel] = r - 0.05; lrout[sel] = r; lsec[sel] = sector(c)
        put(lm, 'tc17_pivot', 'FLOAT_VECTOR', lpiv); put(lm, 'tc17_rin', 'FLOAT', lrin); put(lm, 'tc17_rout', 'FLOAT', lrout); put(lm, 'tc17_sector', 'FLOAT', lsec)
        print('TREE MESH', i, 'segments', len(tcen), 'main', int(main.sum()), 'leaves', li.max() + 1, 'rmax', round(rmax, 3), flush=True)

    g = bpy.data.node_groups.new('TC17_Backdrop_Branch_Season', 'GeometryNodeTree'); N = g.nodes; Lk = g.links
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry'); g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    def mth(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: Lk.new(x, n.inputs[i])
        return n.outputs[0]
    def attr(name, typ='FLOAT'):
        n = N.new('GeometryNodeInputNamedAttribute'); n.data_type = typ; n.inputs['Name'].default_value = name; return n.outputs['Attribute']
    so = N.new('GeometryNodeSelfObject'); oi = N.new('GeometryNodeObjectInfo'); Lk.new(so.outputs[0], oi.inputs['Object'])
    sx = N.new('ShaderNodeSeparateXYZ'); Lk.new(oi.outputs['Location'], sx.inputs[0])
    seed = mth('ADD', mth('MULTIPLY', sx.outputs['X'], 13.7), mth('MULTIPLY', sx.outputs['Y'], 7.3))   # same seed as TC15, so trunk and leaves agree
    r_tree = N.new('FunctionNodeRandomValue'); r_tree.data_type = 'FLOAT'; r_tree.inputs['ID'].default_value = 0; Lk.new(seed, r_tree.inputs['Seed'])
    lv = N.new('ShaderNodeValue'); lv.name = lv.label = 'TC17 Leaf Loss'; drive(g, 'nodes["TC17 Leaf Loss"].outputs[0].default_value', 'v', {'v': 'tc_bg_leaf_loss'})
    loss = mth('ADD', lv.outputs[0], mth('MULTIPLY', mth('SUBTRACT', r_tree.outputs['Value'], 0.5), 0.22), clamp=True)
    r_sec = N.new('FunctionNodeRandomValue'); r_sec.data_type = 'FLOAT'
    Lk.new(mth('ADD', attr('tc17_sector'), 100.0), r_sec.inputs['ID']); Lk.new(seed, r_sec.inputs['Seed'])
    thresh = mth('ADD', mth('MULTIPLY', r_sec.outputs['Value'], 0.50), 0.12)          # each limb dies back at its own loss level
    dieback = mth('DIVIDE', mth('SUBTRACT', loss, thresh), 0.24, clamp=True)
    limit = mth('SUBTRACT', 1.04, mth('MULTIPLY', dieback, 0.98))                     # how far out from the crown centre the limb still reaches
    rin, rout = attr('tc17_rin'), attr('tc17_rout')
    k = mth('DIVIDE', mth('SUBTRACT', limit, rin), mth('MAXIMUM', mth('SUBTRACT', rout, rin), 0.03), clamp=True)
    piv = attr('tc17_pivot', 'FLOAT_VECTOR'); pos = N.new('GeometryNodeInputPosition')
    d = N.new('ShaderNodeVectorMath'); d.operation = 'SUBTRACT'; Lk.new(pos.outputs[0], d.inputs[0]); Lk.new(piv, d.inputs[1])
    sc = N.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; Lk.new(d.outputs[0], sc.inputs[0]); Lk.new(k, sc.inputs['Scale'])
    ad = N.new('ShaderNodeVectorMath'); ad.operation = 'ADD'; Lk.new(sc.outputs[0], ad.inputs[0]); Lk.new(piv, ad.inputs[1])
    sp = N.new('GeometryNodeSetPosition'); Lk.new(gi.outputs[0], sp.inputs['Geometry']); Lk.new(ad.outputs[0], sp.inputs['Position'])
    de = N.new('GeometryNodeDeleteGeometry'); de.domain = 'FACE'; Lk.new(sp.outputs[0], de.inputs['Geometry']); Lk.new(mth('LESS_THAN', k, 0.03), de.inputs['Selection'])
    Lk.new(de.outputs[0], go.inputs[0])
    n_obj = 0
    for o in list(O):
        if o.name.startswith('TC_Backdrop_Tree_') or o.name.startswith('TCP_Backdrop_Trunk_'):
            mo = o.modifiers.new('TC17 seasonal branches', 'NODES'); mo.node_group = g; n_obj += 1   # after TC15 on the leaves
    S['tc17_storm_branches'] = 1
    print('TC17 APPLIED strikes', strikes, 'tree objects', n_obj, flush=True)

if '--apply' in args: apply()
if '--render' in args:
    i = args.index('--render'); out = os.path.abspath(args[i + 1]); os.makedirs(out, exist_ok=True)
    S.render.resolution_x = int(args[i + 3]); S.render.resolution_y = int(args[i + 3]) * 9 // 16; S.eevee.taa_render_samples = int(args[i + 4]); S.render.use_motion_blur = False
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 90
    for f in [int(x) for x in args[i + 2].split(',')]:
        t = time.time(); S.frame_set(f); S.render.filepath = os.path.join(out, 'f_%04d.jpg' % f); bpy.ops.render.render(write_still=True, scene='Scene')
        print('FRAME', f, round(time.time() - t, 1), 'loss', round(S.get('tc_bg_leaf_loss', 0), 3), 'flash', round(S.get('tc_cloud_flash', 0), 2), flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1; bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
