"""TC15: visible rain, background trees that shed and regrow, drifting clouds.
blender -b TimeCapsule.blend --python weather_pass.py -- [--render DIR FRAMES RESX SAMPLES] [--save]     Guard: tc15_weather_pass."""
import bpy, sys, os, math, time
import numpy as np
S = bpy.data.scenes['Scene']; O = S.objects; M = bpy.data.materials
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc14_shovel_shape') == 1 and not S.get('tc15_weather_pass')
F0, F1 = 1201, 6240
NOON = 0.41; P = (F1 - F0) / (24 + NOON + 0.145)            # the day/year cycle of the TC13 pass
def phase(f): return NOON + (f - F1) / P
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

# ---------------- 1. rain ----------------
rg = O['TC_Polish_Rain'].modifiers[0].node_group; RN = rg.nodes
RN['2200 live drops maximum'].inputs['Count'].default_value = 3800
c = RN['Thin tapered water streak']; c.inputs['Radius Top'].default_value = 0.0011; c.inputs['Radius Bottom'].default_value = 0.0026; c.inputs['Depth'].default_value = 0.30
RN['TC2 Streak-tip clearance'].inputs[1].default_value = 0.15      # half the streak length, so tips still stop on the surface
dm = M['TC_Polish_Raindrop']; b = next(n for n in dm.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
b.inputs['Base Color'].default_value = (0.80, 0.88, 0.96, 1); b.inputs['Alpha'].default_value = 0.62
b.inputs['Emission Color'].default_value = (0.78, 0.87, 1.0, 1)   # streaks catch the sky light; dimmed with the daylight
drive(dm.node_tree, 'nodes["%s"].inputs[%d].default_value' % (b.name, list(b.inputs).index(b.inputs['Emission Strength'])), '0.32*(0.10+0.90*d)', {'d': 'tc_day'})

# drops right in front of the lens would cross the frame as thick bars: fade streaks out closer than about 4 m
dn = dm.node_tree; cam_d = dn.nodes.new('ShaderNodeCameraData')
nearf = dn.nodes.new('ShaderNodeMapRange'); nearf.inputs['From Min'].default_value = 1.5; nearf.inputs['From Max'].default_value = 4.5; dn.links.new(cam_d.outputs['View Distance'], nearf.inputs['Value'])
al = dn.nodes.new('ShaderNodeMath'); al.operation = 'MULTIPLY'; al.inputs[1].default_value = b.inputs['Alpha'].default_value; dn.links.new(nearf.outputs[0], al.inputs[0]); dn.links.new(al.outputs[0], b.inputs['Alpha'])

# ---------------- 2. background trees ----------------
env = [(F0, 0.05), (1345, 0.30), (1921, 0.0), (2400, 0.0), (2700, 0.20), (3300, 0.72), (3960, 0.72), (4440, 0.30), (4800, 0.15), (4950, 0.38), (5400, 0.30), (6000, 0.15), (F1, 0.10)]
ex, ey = zip(*env); pairs = [(1, 0.0), (F0 - 1, 0.0)]
for f in range(F0, F1 + 1):
    season = 0.5 + 0.5 * math.cos(2 * math.pi * (phase(f) - 0.02))            # thinnest crowns at each sunrise (= new year), fullest mid-cycle
    edge = min(1.0, (f - F0) / 100, (F1 - f) / 100)
    pairs.append((f, min(0.93, float(np.interp(f, ex, ey)) + 0.24 * season * edge)))
pairs += [(F1 + 1, 0.10), (7200, 0.06)]
key_prop('tc_bg_leaf_loss', pairs)
g = bpy.data.node_groups.new('TC15_Backdrop_Leaf_Season', 'GeometryNodeTree'); N = g.nodes; L = g.links
g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry'); g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
def mth(op, a, b=None, clamp=False):
    n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    for i, x in enumerate((a, b)):
        if x is None: continue
        if isinstance(x, (int, float)): n.inputs[i].default_value = x
        else: L.new(x, n.inputs[i])
    return n.outputs[0]
so = N.new('GeometryNodeSelfObject'); oi = N.new('GeometryNodeObjectInfo'); L.new(so.outputs[0], oi.inputs['Object'])
sx = N.new('ShaderNodeSeparateXYZ'); L.new(oi.outputs['Location'], sx.inputs[0])
seed = mth('ADD', mth('MULTIPLY', sx.outputs['X'], 13.7), mth('MULTIPLY', sx.outputs['Y'], 7.3))
isl = N.new('GeometryNodeInputMeshIsland')
r_leaf = N.new('FunctionNodeRandomValue'); r_leaf.data_type = 'FLOAT'; L.new(isl.outputs['Island Index'], r_leaf.inputs['ID']); L.new(seed, r_leaf.inputs['Seed'])
r_tree = N.new('FunctionNodeRandomValue'); r_tree.data_type = 'FLOAT'; r_tree.inputs['ID'].default_value = 0; L.new(seed, r_tree.inputs['Seed'])
lv = N.new('ShaderNodeValue'); lv.name = lv.label = 'TC15 Leaf Loss'; drive(g, 'nodes["TC15 Leaf Loss"].outputs[0].default_value', 'v', {'v': 'tc_bg_leaf_loss'})
loss = mth('ADD', lv.outputs[0], mth('MULTIPLY', mth('SUBTRACT', r_tree.outputs['Value'], 0.5), 0.22), clamp=True)       # every tree runs a little early or late
loss = mth('MULTIPLY', loss, mth('GREATER_THAN', lv.outputs[0], 0.001))                                            # exactly full crowns when the film says so
keep = mth('DIVIDE', mth('SUBTRACT', mth('SUBTRACT', 1.0, loss), mth('MULTIPLY', r_leaf.outputs['Value'], 0.85)), 0.15, clamp=True)   # each leaf shrinks, then drops, in its own turn
sc = N.new('GeometryNodeScaleElements'); sc.domain = 'FACE'; L.new(gi.outputs[0], sc.inputs['Geometry']); L.new(keep, sc.inputs['Scale'])
de = N.new('GeometryNodeDeleteGeometry'); de.domain = 'FACE'; L.new(sc.outputs[0], de.inputs['Geometry']); L.new(mth('LESS_THAN', keep, 0.04), de.inputs['Selection'])
L.new(de.outputs[0], go.inputs[0])
trees = [o for o in O if o.name.startswith('TC_Backdrop_Tree_')]
for o in trees:
    m = o.modifiers.new('TC15 seasonal leaves', 'NODES'); m.node_group = g
for i in range(3):                                                  # leaves yellow before they fall
    nt = M['TCP_Foliage_%d' % i].node_tree; pv = nt.nodes['Nature Leaf Pigment Variation']; green = tuple(pv.inputs['Color1'].default_value)
    v = nt.nodes.new('ShaderNodeValue'); v.name = v.label = 'TC15 Leaf Loss'; drive(nt, 'nodes["TC15 Leaf Loss"].outputs[0].default_value', 'min(1,max(0,1.5*v-0.12))', {'v': 'tc_bg_leaf_loss'})
    mx = nt.nodes.new('ShaderNodeMixRGB'); mx.inputs['Color1'].default_value = green; mx.inputs['Color2'].default_value = ((0.25, 0.19, 0.035, 1), (0.29, 0.17, 0.035, 1), (0.22, 0.20, 0.05, 1))[i]
    nt.links.new(v.outputs[0], mx.inputs['Fac']); nt.links.new(mx.outputs[0], pv.inputs['Color1'])

# ---------------- 3. clouds ----------------
turn = 0.30 * (F1 - F0) / P                                        # 0.30 rad of sky drift per time-lapse cycle
key_prop('tc_cloud_drift', [(1, 0.0), (F0 - 1, 0.07), (F0, 0.07), (F1, 0.07 + turn), (F1 + 1, 0.07 + turn), (7200, 0.13 + turn)])
W = S.world.node_tree; WN = W.nodes; WL = W.links
mp = WN['Story Sky Orientation']; base = mp.inputs['Rotation'].default_value[2]
drive(W, 'nodes["Story Sky Orientation"].inputs[%d].default_value' % list(mp.inputs).index(mp.inputs['Rotation']), '%r+v' % base, {'v': 'tc_cloud_drift'}, idx=2)
nz = WN.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'; nz.name = 'TC15 Cloud Churn'; nz.inputs['Scale'].default_value = 2.6; nz.inputs['Detail'].default_value = 2.0
WL.new(mp.outputs[0], nz.inputs['Vector'])
drive(W, 'nodes["TC15 Cloud Churn"].inputs[%d].default_value' % list(nz.inputs).index(nz.inputs['W']), '5.0*v', {'v': 'tc_cloud_drift'})
off = WN.new('ShaderNodeVectorMath'); off.operation = 'SUBTRACT'; WL.new(nz.outputs['Color'], off.inputs[0]); off.inputs[1].default_value = (0.5, 0.5, 0.5)
scl = WN.new('ShaderNodeVectorMath'); scl.operation = 'SCALE'; WL.new(off.outputs[0], scl.inputs[0]); scl.inputs['Scale'].default_value = 0.05
add = WN.new('ShaderNodeVectorMath'); add.operation = 'ADD'; WL.new(mp.outputs[0], add.inputs[0]); WL.new(scl.outputs[0], add.inputs[1])
for n in WN:                                                        # the cloud images are looked up through the slowly changing warp, so clouds billow as they drift
    if n.bl_idname == 'ShaderNodeTexEnvironment':
        for l in list(n.inputs['Vector'].links): WL.remove(l)
        WL.new(add.outputs[0], n.inputs['Vector'])
S['tc15_weather_pass'] = 1
print('TC15 APPLIED trees', len(trees), flush=True)
if '--render' in args:
    i = args.index('--render'); out = args[i + 1]; os.makedirs(out, exist_ok=True)
    S.render.resolution_x = int(args[i + 3]); S.render.resolution_y = int(args[i + 3]) * 9 // 16; S.eevee.taa_render_samples = int(args[i + 4]); S.render.use_motion_blur = False
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 90
    for f in [int(x) for x in args[i + 2].split(',')]:
        t = time.time(); S.frame_set(f); S.render.filepath = os.path.join(out, 'w_%04d.jpg' % f); bpy.ops.render.render(write_still=True, scene='Scene'); print('FRAME', f, round(time.time() - t, 1), flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1; bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
