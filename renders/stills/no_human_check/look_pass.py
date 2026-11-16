import bpy, sys, os, time
S = bpy.data.scenes['Scene']; O = S.objects
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
assert S.get('tc11_old_shovel') == 1 and not S.get('tc12_look_pass')
M = bpy.data.materials
def age_node(nt, prop, name='TC12 Age'):
    a = nt.nodes.new('ShaderNodeValue'); a.name = a.label = name
    d = nt.driver_add('nodes["%s"].outputs[0].default_value' % name).driver; d.type = 'SUM'
    v = d.variables.new(); v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'SCENE'; v.targets[0].id = S; v.targets[0].data_path = '["%s"]' % prop
    return a
def weather(m, prop, tones, rough, scale, gain, up=False):
    """noise-masked ageing layer over the existing base colour / roughness, growing with a keyed scene property"""
    nt = m.node_tree; N = nt.nodes; L = nt.links
    p = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled' and n.outputs[0].is_linked)
    age = age_node(nt, prop); tc = N.new('ShaderNodeTexCoord')
    n1 = N.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = scale; n1.inputs['Detail'].default_value = 7.0; L.new(tc.outputs['Object'], n1.inputs['Vector'])
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = scale * 6; L.new(tc.outputs['Object'], n2.inputs['Vector'])
    thr = N.new('ShaderNodeMath'); thr.operation = 'MULTIPLY_ADD'; L.new(age.outputs[0], thr.inputs[0]); thr.inputs[1].default_value = -gain; thr.inputs[2].default_value = 1.0
    sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; L.new(n1.outputs[0], sub.inputs[0]); L.new(thr.outputs[0], sub.inputs[1])
    mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.use_clamp = True; L.new(sub.outputs[0], mul.inputs[0]); mul.inputs[1].default_value = 4.0
    mask = mul.outputs[0]
    if up:      # lichen prefers the faces that see the sky
        g = N.new('ShaderNodeNewGeometry'); sx = N.new('ShaderNodeSeparateXYZ'); L.new(g.outputs['Normal'], sx.inputs[0])
        u = N.new('ShaderNodeMath'); u.operation = 'MULTIPLY_ADD'; u.use_clamp = True; L.new(sx.outputs['Z'], u.inputs[0]); u.inputs[1].default_value = 1.3; u.inputs[2].default_value = 0.25
        mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; L.new(mask, mm.inputs[0]); L.new(u.outputs[0], mm.inputs[1]); mask = mm.outputs[0]
    tone = N.new('ShaderNodeMixRGB'); tone.inputs['Color1'].default_value = (*tones[0], 1); tone.inputs['Color2'].default_value = (*tones[1], 1); L.new(n2.outputs[0], tone.inputs['Fac'])
    def over(sock, target):
        mx = N.new('ShaderNodeMixRGB'); L.new(mask, mx.inputs['Fac'])
        if sock.is_linked:
            frm = sock.links[0].from_socket; L.remove(sock.links[0]); L.new(frm, mx.inputs['Color1'])
        else:
            dv = sock.default_value; mx.inputs['Color1'].default_value = tuple(dv) if hasattr(dv, '__len__') else (dv, dv, dv, 1)
        if isinstance(target, float): mx.inputs['Color2'].default_value = (target, target, target, 1)
        else: L.new(target, mx.inputs['Color2'])
        L.new(mx.outputs[0], sock)
    over(p.inputs['Base Color'], tone.outputs[0]); over(p.inputs['Roughness'], rough)
# --- passage of time on the remaining items ---
S['tc_stone_age'] = 0.0
for f, v in ((1, 0.0), (1200, 0.0), (2400, 0.35), (3600, 0.45), (4800, 0.7), (6240, 1.0), (7200, 1.0)):   # lichen grows in the wet years, stalls in the drought
    S['tc_stone_age'] = v; S.keyframe_insert('["tc_stone_age"]', frame=f)
weather(M['TC_Marker_Stone'], 'tc_stone_age', ((0.20, 0.23, 0.12), (0.42, 0.40, 0.22)), 0.97, 9.0, 0.62, up=True)
weather(M['TC_Paper'], 'tc_capsule_age', ((0.52, 0.41, 0.23), (0.70, 0.60, 0.40)), 0.92, 16.0, 1.25)
env = M['TC_Envelope']; next(n for n in env.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled').inputs['Roughness'].default_value = 0.72   # was glossy 0.18
weather(env, 'tc_capsule_age', ((0.55, 0.45, 0.27), (0.72, 0.63, 0.44)), 0.9, 11.0, 1.2)
# photograph: colours fade and warm evenly with the capsule's age
ph = M['TC_Photo']; nt = ph.node_tree; N = nt.nodes; L = nt.links
hs = next(n for n in N if n.bl_idname == 'ShaderNodeHueSaturation'); p = next(n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled')
age = age_node(nt, 'tc_capsule_age')
sat = N.new('ShaderNodeMath'); sat.operation = 'MULTIPLY_ADD'; L.new(age.outputs[0], sat.inputs[0]); sat.inputs[1].default_value = -0.33; sat.inputs[2].default_value = 0.88
L.new(sat.outputs[0], hs.inputs['Saturation'])          # fresh print 0.88 -> found print 0.55 (the old constant)
fac = N.new('ShaderNodeMath'); fac.operation = 'MULTIPLY'; L.new(age.outputs[0], fac.inputs[0]); fac.inputs[1].default_value = 0.85
warm = N.new('ShaderNodeMixRGB'); warm.blend_type = 'MULTIPLY'; warm.inputs['Color2'].default_value = (1.0, 0.91, 0.74, 1); L.new(fac.outputs[0], warm.inputs['Fac'])
L.new(hs.outputs[0], warm.inputs['Color1'])
lift = N.new('ShaderNodeMixRGB'); lift.blend_type = 'MIX'; lift.inputs['Color2'].default_value = (0.62, 0.55, 0.42, 1); L.new(warm.outputs[0], lift.inputs['Color1'])
lf = N.new('ShaderNodeMath'); lf.operation = 'MULTIPLY'; L.new(age.outputs[0], lf.inputs[0]); lf.inputs[1].default_value = 0.16; L.new(lf.outputs[0], lift.inputs['Fac'])   # faded blacks
for l in list(p.inputs['Base Color'].links): L.remove(l)
L.new(lift.outputs[0], p.inputs['Base Color'])
# pit interior read as a flat lit sheet: darken the soil with depth so it reads as a hole
for mn, k in (('TC5_Topsoil', 0.78), ('TC5_Subsoil', 0.5), ('TC5_Deep_soil', 0.34)):
    nt = M[mn].node_tree; p = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    mx = nt.nodes.new('ShaderNodeMixRGB'); mx.blend_type = 'MULTIPLY'; mx.inputs['Fac'].default_value = 1.0; mx.inputs['Color2'].default_value = (k, k * 0.96, k * 0.9, 1)
    frm = p.inputs['Base Color'].links[0].from_socket; nt.links.remove(p.inputs['Base Color'].links[0]); nt.links.new(frm, mx.inputs['Color1']); nt.links.new(mx.outputs[0], p.inputs['Base Color'])
# --- lighting / shading ---
for n in ('TC_Sun', 'TC_Lightning'):
    d = O[n].data; d.use_shadow_jitter = True; d.shadow_jitter_overblur = 10.0
O['TC_Sun'].data.angle = 0.021            # soft-edged penumbra instead of razor-sharp shadows (about 1.2 degrees)
for n in ('TC_Polish_SkyFill', 'TC_Story_Ground_Bounce_Fill'):
    O[n].data.use_shadow_jitter = True
S.eevee.shadow_ray_count = 3
S['tc12_look_pass'] = 1
print('LOOK PASS APPLIED', flush=True)
if '--render' in args:
    outdir = args[args.index('--render') + 1]; os.makedirs(outdir, exist_ok=True)
    S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 92
    for f in [int(x) for x in args[args.index('--render') + 2].split(',')]:
        t = time.time(); S.frame_set(f); S.render.filepath = os.path.join(outdir, 'p_%04d.jpg' % f); bpy.ops.render.render(write_still=True, scene='Scene')
        print('FRAME', f, 'seconds', round(time.time() - t, 1), flush=True)
    print('RENDERED', flush=True)
elif '--save' in args:
    bpy.context.preferences.filepaths.save_version = 1
    bpy.ops.wm.save_mainfile()
    print('SAVED', S.render.resolution_x, S.render.resolution_y, S.eevee.taa_render_samples, S.render.use_motion_blur, len(bpy.data.actions), flush=True)
