"""TC16: clouds slide overhead as a layer instead of the whole sky turning.
blender -b TimeCapsule.blend --python cloud_flow.py -- [--render DIR FRAMES RESX SAMPLES] [--save]     Guard: tc16_cloud_flow.

A sky direction d meets a flat cloud layer at p = d.xy / d.z. Moving the layer by o gives the direction (d.xy + o d.z, d.z):
fast overhead, vanishing at the horizon, one wind direction. The sky images are looked up through that shifted direction.
A shift cannot grow for ever, so two lookups run half a period apart, each from -A/2 to +A/2, cross-faded with triangle
weights (the flow-map method); the fade also lets the clouds change as they travel."""
import bpy, sys, os, time
S = bpy.data.scenes['Scene']
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc15_weather_pass') == 1 and not S.get('tc16_cloud_flow')
F0, F1 = 1201, 6240
AMP = 0.8                       # travel of one lookup, in layer heights
SLOW, FAST = 0.012, 0.25        # layer heights per second of film: real-time sections / time-lapse
WIND = (0.8, 0.6)
def fcurves(idb):
    ad = idb.animation_data; out = []
    if ad and ad.action:
        for layer in ad.action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    if ad.action_slot is None or cb.slot_handle == ad.action_slot.handle: out += list(cb.fcurves)
    return out
def drive(idb, path, expr, idx=-1):
    fc = idb.driver_add(path, idx) if idx >= 0 else idb.driver_add(path); d = fc.driver; d.type = 'SCRIPTED'
    v = d.variables.new(); v.name = 'v'; v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'SCENE'; v.targets[0].id = S; v.targets[0].data_path = '["tc_cloud_drift"]'
    d.expression = expr
# tc_cloud_drift now counts flow periods
fc = next(f for f in fcurves(S) if f.data_path == '["tc_cloud_drift"]')
a = (F0 - 1) / 24 * SLOW / AMP; b = a + (F1 - F0) / 24 * FAST / AMP; c = b + (7200 - F1) / 24 * SLOW / AMP
while len(fc.keyframe_points): fc.keyframe_points.remove(fc.keyframe_points[0], fast=True)
for fr, v in ((1, 0.0), (F0 - 1, a), (F0, a), (F1, b), (F1 + 1, b), (7200, c)):
    fc.keyframe_points.insert(fr, v, options={'FAST'}).interpolation = 'LINEAR'
fc.update()
W = S.world.node_tree; N = W.nodes; L = W.links
mp = N['Story Sky Orientation']
ri = list(mp.inputs).index(mp.inputs['Rotation'])
base_rot = float(W.animation_data.drivers.find('nodes["Story Sky Orientation"].inputs[%d].default_value' % ri, index=2).driver.expression.split('+')[0])
W.driver_remove('nodes["Story Sky Orientation"].inputs[%d].default_value' % ri, 2)       # the sky itself stands still again
mp.inputs['Rotation'].default_value[2] = base_rot
churn = N['TC15 Cloud Churn']; wi = list(churn.inputs).index(churn.inputs['W'])
W.driver_remove('nodes["TC15 Cloud Churn"].inputs[%d].default_value' % wi); drive(W, 'nodes["TC15 Cloud Churn"].inputs[%d].default_value' % wi, '0.5*v')
envs = [n for n in N if n.bl_idname == 'ShaderNodeTexEnvironment']
base = envs[0].inputs['Vector'].links[0].from_socket                # sky direction with the small churn warp
base.node.inputs[1].links[0].from_node.inputs['Scale'].default_value = 0.03
sep = N.new('ShaderNodeSeparateXYZ'); L.new(base, sep.inputs[0])
up = N.new('ShaderNodeMath'); up.operation = 'MAXIMUM'; up.inputs[1].default_value = 0.0; L.new(sep.outputs['Z'], up.inputs[0])
def value(name, expr):
    n = N.new('ShaderNodeValue'); n.name = n.label = name; drive(W, 'nodes["%s"].outputs[0].default_value' % name, expr); return n.outputs[0]
dirs = []
for k in (0, 1):
    s = value('TC16 Flow Shift %d' % k, '((v+%g)%%1.0-0.5)*%g' % (0.5 * k, AMP))
    wind = N.new('ShaderNodeVectorMath'); wind.operation = 'SCALE'; wind.inputs[0].default_value = (WIND[0], WIND[1], 0.0); L.new(s, wind.inputs['Scale'])
    lift = N.new('ShaderNodeVectorMath'); lift.operation = 'SCALE'; L.new(wind.outputs[0], lift.inputs[0]); L.new(up.outputs[0], lift.inputs['Scale'])
    add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'; L.new(base, add.inputs[0]); L.new(lift.outputs[0], add.inputs[1])
    nrm = N.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L.new(add.outputs[0], nrm.inputs[0]); dirs.append(nrm.outputs[0])
fade = value('TC16 Flow Fade', 'fabs(2*((v%1.0)-0.5))')            # weight of the second lookup: 1 when the first one wraps
for e in envs:
    twin = N.new('ShaderNodeTexEnvironment'); twin.image = e.image; twin.projection = e.projection; twin.interpolation = e.interpolation; twin.name = e.name + ' flow B'
    for l in list(e.inputs['Vector'].links): L.remove(l)
    L.new(dirs[0], e.inputs['Vector']); L.new(dirs[1], twin.inputs['Vector'])
    mx = N.new('ShaderNodeMixRGB'); L.new(fade, mx.inputs['Fac']); L.new(e.outputs['Color'], mx.inputs['Color1']); L.new(twin.outputs['Color'], mx.inputs['Color2'])
    for l in list(e.outputs['Color'].links):
        if l.to_node != mx:
            to = l.to_socket; L.remove(l); L.new(mx.outputs[0], to)
S['tc16_cloud_flow'] = 1
print('TC16 APPLIED envs', len(envs), 'drift', round(a, 3), round(b, 3), round(c, 3), flush=True)
if '--render' in args:
    i = args.index('--render'); out = args[i + 1]; os.makedirs(out, exist_ok=True)
    S.render.resolution_x = int(args[i + 3]); S.render.resolution_y = int(args[i + 3]) * 9 // 16; S.eevee.taa_render_samples = int(args[i + 4]); S.render.use_motion_blur = False
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 90
    for f in [int(x) for x in args[i + 2].split(',')]:
        S.frame_set(f); S.render.filepath = os.path.join(out, 'c_%04d.jpg' % f); bpy.ops.render.render(write_still=True, scene='Scene'); print('FRAME', f, flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1; bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
