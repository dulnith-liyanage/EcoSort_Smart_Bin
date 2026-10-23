"""FreeCAD CAD generator. Run Build.FCMacro, or FreeCAD Python build.py --headless.
Printable geometry is separate from simplified purchased-hardware references.
"""
import json
import math
import sys
from pathlib import Path

if Path('/Applications/FreeCAD.app/Contents/Resources/lib').exists():
    sys.path.append('/Applications/FreeCAD.app/Contents/Resources/lib')
import FreeCAD as A
import Part
import MeshPart

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
(OUT / 'stl').mkdir(parents=True, exist_ok=True)
(OUT / 'step').mkdir(exist_ok=True)
P = json.loads((ROOT / 'parameters.json').read_text())
V = A.Vector
doc = A.newDocument('EcoSort_Complete')
groups = {n: doc.addObject('App::DocumentObjectGroup', n) for n in
          ['Printed_parts', 'Purchased_hardware', 'Bins_reference', 'Timber_reference']}
checks = {}
def box(x,y,z,p=(0,0,0)): return Part.makeBox(x,y,z,V(*p))
def hole(d,h,p,axis=(0,0,1)): return Part.makeCylinder(d/2,h,V(*p),V(*axis))
def moved(s,p,angle=0):
    s=s.copy()
    s.rotate(V(),V(0,0,1),angle)
    s.translate(V(*p))
    return s
def add(name,s,group='Printed_parts',color=(0.15,0.6,0.65),note=''):
    o=doc.addObject('Part::Feature',name)
    o.Label=name.replace('_',' ')
    o.Shape=s
    o.addProperty('App::PropertyString','DesignNote');o.DesignNote=note
    groups[group].addObject(o)
    if A.GuiUp:
        o.ViewObject.ShapeColor=color
        o.ViewObject.DisplayMode='Flat Lines'
        o.ViewObject.show()
    return o
def printable(name,s,qty,p,angle=0,show=True):
    s=s.removeSplitter()
    assert s.isValid() and len(s.Solids)==1 and s.Volume>0,name
    mesh=MeshPart.meshFromShape(Shape=s,LinearDeflection=0.3,AngularDeflection=0.4,Relative=False)
    assert mesh.isSolid(),name
    mesh.write(str(OUT/'stl'/f'{name}.stl'))
    s.exportStep(str(OUT/'step'/f'{name}.step'))
    checks[name]={'quantity':qty,'valid_solid':True,'watertight':True,'triangles':mesh.CountFacets,
                  'size_mm':[round(v,2) for v in [s.BoundBox.XLength,s.BoundBox.YLength,s.BoundBox.ZLength]]}
    if show: add(name,moved(s,p,angle))
    return s
bh=P['bin_height'];bt=P['base_thickness'];ph=P['pedestal_height']
span=P['base_span'];aw=P['base_arm_width']
base=box(aw,span,bt,(-aw/2,-span/2,0)).fuse(box(span,aw,bt,(-span/2,-aw/2,0)))
for x in [-P['rim_bolt_x'],P['rim_bolt_x']]:
    for y in [-P['rim_bolt_y'],P['rim_bolt_y']]:
        base=base.cut(box(6,24,bt+2,(x-3,y-12,-1)))
for x in [-22,22]:
    for y in [-22,22]: base=base.cut(hole(4.5,bt+2,(x,y,-1)))
printable('01_cross_base',base,1,(0,0,bh))
ped=box(60,60,ph,(-30,-30,0)).cut(box(48,48,ph+2,(-24,-24,-1)))
ped=ped.fuse(box(94,80,8,(-47,-40,ph))).cut(box(30,30,10,(-15,-15,ph-1)))
ped=ped.cut(box(30,8,30,(-15,-31,ph-34)))
for x in [-30,30]: ped=ped.cut(box(4,24,10,(x-2,-12,ph-1)))
for x in [-5,5]:
    for y in [-24,24]: ped=ped.cut(box(3.6,12,10,(x-1.8,y-6,ph-1)))
for x in [-22,22]:
    for y in [-22,22]:
        # Internal feet carry the base bolts; accessible through hollow tower.
        ped=ped.fuse(box(10,10,6,(x-5,y-5,0)))
        ped=ped.cut(hole(4.5,8,(x,y,-1)))
printable('02_motor_pedestal',ped,1,(0,0,bh+bt))
# Shoe toes point along X into the appropriate bin. No assumed hole in bin.
shoe=box(34,30,8,(-20,-15,0)).cut(hole(5.6,10,(0,0,-1)))
printable('03_rim_shoe',shoe,4,(P['rim_bolt_x'],P['rim_bolt_y'],bh-P['rim_depth']-8))
for x,y in [(-P['rim_bolt_x'],P['rim_bolt_y']),(-P['rim_bolt_x'],-P['rim_bolt_y']),(P['rim_bolt_x'],-P['rim_bolt_y'])]:
    add('Rim_shoe_copy',moved(shoe,(x,y,bh-P['rim_depth']-8),180 if x<0 else 0))
kit_z=bh+bt+ph+8
pivot=kit_z+P['kit_pivot_height']
adapter=box(90,70,6,(-45,-35,0))
for x in [-20,20]: adapter=adapter.cut(box(3.6,24,8,(x-1.8,-12,-1)))
for x in [-36,36]:
    for y in [-26,26]: adapter=adapter.cut(hole(4.5,8,(x,y,-1)))
printable('04_tray_adapter',adapter,1,(0,0,pivot-6))
mx,my=P['mast_x'],P['mast_y']
# Separate rear-bin clip; two M5 screws with nuts push pads against the rim.
clip=box(100,93,6,(-50,-53,0))
for y in [-53,-9]: clip=clip.fuse(box(100,12,40,(-50,y,-40)))
clip=clip.fuse(box(34,34,70,(-17,-17,6)))
e=P['timber_size']+P['timber_clearance']
clip=clip.cut(box(e,e,72,(-e/2,-e/2,6)))
for z in [28,55]: clip=clip.cut(hole(4.5,38,(-19,0,z),(1,0,0)))
for x in [-35,35]: clip=clip.cut(hole(5.6,14,(x,-10,-20),(0,1,0)))
# Open, insulated driver shelf on the dry side of the rear bin.
clip=clip.fuse(box(80,50,6,(45,0,0)))
for x in [55,108]:
    for y in [5,40]: clip=clip.cut(box(6,4,8,(x,y,-1)))
printable('05_rear_clip_and_driver_shelf',clip,1,(mx,my,bh))
pad=box(24,6,24,(-12,-3,-12)).cut(hole(5.8,3,(0,1,0),(0,1,0)))
printable('06_pressure_pad',pad,2,(mx-35,my-22,bh-20))
add('Second_pressure_pad',moved(pad,(mx+35,my-22,bh-20)))
# Pi and camera share the same open carrier; no long camera ribbon required.
plate_z=pivot+P['camera_clearance']+14
boom_z=plate_z+57
theta=-math.degrees(math.atan2(mx,my))
elbow=box(34,34,64,(-17,-17,-64)).cut(box(e,e,60,(-e/2,-e/2,-65)))
arm=box(34,72,34,(-17,-64,-17)).cut(box(e,74,e,(-e/2,-65,-e/2)))
elbow=elbow.fuse(moved(arm,(0,0,0),theta))
for z in [-48,-28]: elbow=elbow.cut(hole(4.5,38,(-19,0,z),(1,0,0)))
elbow=elbow.cut(moved(hole(4.5,38,(-19,-42,0),(1,0,0)),(0,0,0),theta))
printable('07_timber_elbow',elbow,1,(mx,my,boom_z))
carrier=box(175,155,4,(-55,-45,0))
carrier=carrier.cut(box(10,10,6,(-32.5,-5,-1)))
for x in [-38,-17]:
    for y in [-6.25,6.25]: carrier=carrier.cut(hole(2.4,6,(x,y,-1)))
for x in [10,90]:
    for y in [23,103]: carrier=carrier.cut(box(12,4,6,(x,y,-1)))
socket=box(34,40,34,(-17,-20,40)).cut(box(e,42,e,(-e/2,-21,57-e/2)))
socket=socket.cut(hole(4.5,38,(-19,0,57),(1,0,0)))
carrier=carrier.fuse(socket)
for x in [-26,17]: carrier=carrier.fuse(box(9,40,44,(x,-20,0)))
printable('08_shared_pi_camera_carrier',carrier,1,(0,0,plate_z),theta)
coupon=box(80,30,3)
for x in [0,38]:coupon=coupon.fuse(box(6,30,22,(x,0,3)))
coupon=coupon.cut(hole(5.6,8,(37,15,14),(1,0,0)))
coupon=coupon.fuse(box(28,28,28,(50,1,3))).cut(box(e,e,30,(64-e/2,15-e/2,3)))
printable('09_rim_and_timber_fit_coupon',coupon,1,(0,0,0),show=False)
# Orient shared board with the boom; Pi case offset is kept beside camera.
def ref(name,s,color=(0.15,0.18,0.2),note='Unmeasured visual reference; not printable.'):
    return add(name,s,'Purchased_hardware',color,note)
ref('Existing_cased_Pi_5',moved(box(P['case_length'],P['case_width'],P['case_height'],(5,28,4)),(0,0,plate_z),theta),(0.85,0.85,0.85))
cam=box(25,24,1,(-40,-12,-7)).fuse(hole(6,6,(-27.5,0,-13)))
ref('Camera_V2_lens_down',moved(cam,(0,0,plate_z),theta),(0.1,0.5,0.2))
ref('PCA9685_reference',box(62,26,12,(mx+52,my+12,bh+12)),(0.1,0.3,0.7))
servo=box(19.7,40.7,42.9,(-9.85,-20.35,0)).fuse(box(19.7,54,3,(-9.85,-27,28)))
ref('MG996R_pan',moved(servo,(0,0,kit_z+3)))
for x in [-5,5]:
    for y in [-24,24]:
        ref('Pan_servo_M3_standoff_REFERENCE',hole(7,31,(x,y,kit_z)).cut(hole(3.4,33,(x,y,kit_z-1))),
            (0.6,0.6,0.6),'Purchased adjustable spacers; 31 mm height and hole spacing are provisional.')
tilt=servo.copy();tilt.rotate(V(),V(0,1,0),90)
ref('MG996R_tilt',moved(tilt,(-22,0,pivot-18)))
ref('RB0051_pan_bracket',box(60,54,3,(-30,-27,kit_z+48)).fuse(box(3,54,27,(-30,-27,kit_z+48))))
u=box(68,60,3,(-34,-30,pivot-9))
for x in [-34,31]:u=u.fuse(box(3,60,20,(x,-30,pivot-29)))
ref('RB0051_tilt_bracket',u)
tray_ref=ref('Existing_tray',box(P['tray_length'],P['tray_width'],5,(-P['tray_length']/2,-P['tray_width']/2,pivot)),(0.25,0.55,0.3))
if A.GuiUp: tray_ref.ViewObject.Transparency=35
# Rounded bins are reference shells, not measured recreations of the photograph.
def rounded(w,h,r):
    s=box(w-2*r,w,h,(-w/2+r,-w/2,0)).fuse(box(w,w-2*r,h,(-w/2,-w/2+r,0)))
    for x in [-w/2+r,w/2-r]:
        for y in [-w/2+r,w/2-r]:s=s.fuse(hole(2*r,h,(x,y,0)))
    return s.removeSplitter()
bw=P['bin_width'];r=P['bin_corner_radius']
shell=rounded(bw,bh,r).cut(moved(rounded(bw-8,bh,r-4),(0,0,4)))
rim=rounded(bw,P['rim_depth'],r).cut(moved(rounded(bw-32,P['rim_depth']+2,r-16),(0,0,-1)))
shell=shell.fuse(moved(rim,(0,0,bh-P['rim_depth'])))
bin_shapes=[]
for i,(x,y) in enumerate([(-1,-1),(1,-1),(-1,1),(1,1)]):
    bin_shape=moved(shell,(x*(bw+P['bin_gap'])/2,y*(bw+P['bin_gap'])/2,0))
    bin_shapes.append(bin_shape)
    add(f'Bin_{i+1}_REFERENCE',bin_shape,
        'Bins_reference',(0.7,0.68,0.5) if x<0 else (0.75,0.4,0.55),'Rounded, solid-wall stand-in for the slotted baskets; measure before printing.')
upright=boom_z-5-(bh+6)
arm_length=math.hypot(mx,my)+20
add('Timber_upright',box(20,20,upright,(mx-10,my-10,bh+6)),'Timber_reference',(0.65,0.45,0.25))
add('Timber_boom',moved(box(20,arm_length,20,(-10,-arm_length,-10)),(mx,my,boom_z),theta),'Timber_reference',(0.65,0.45,0.25))
doc.recompute()
complete_parts=[o for o in doc.Objects if o.TypeId=='Part::Feature']
assert len(complete_parts)==30
Part.export(complete_parts,str(OUT/'complete_assembly.step'))
doc.saveAs(str(OUT/'complete_assembly.FCStd'))
# Conservative geometric envelope: includes full tray half-diagonal at 65 deg.
half_diagonal=math.hypot(P['tray_length']/2,P['tray_width']/2)
clearance=pivot-half_diagonal*math.sin(math.radians(65))-bh
assert clearance>0, 'Tray envelope reaches rim height: increase pedestal height.'
checks['layout']={'tray_rim_envelope_clearance_mm':round(clearance,1),
 'camera_to_tray_mm':round(P['camera_clearance']+1,1),'timber_upright_cut_mm':round(upright,1),
 'timber_boom_cut_mm':round(arm_length,1),'mast_to_axis_mm':round(math.hypot(mx,my),1),
 'not_verified':['bin fit','bracket screw pattern','tray attachment','load/torque','waste trajectory','wire routing','camera crop/focus']}
for o in groups['Printed_parts'].Group:
    overlap=sum(o.Shape.common(b).Volume for b in bin_shapes)
    assert overlap<0.01, f'{o.Name} intersects reference bin walls: {overlap}'
checks['layout']['printed_parts_vs_reference_bins_overlap_mm3']=0
(OUT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
# Retain a separate inspection file for just the centre mechanism.
motor_doc=A.newDocument('EcoSort_Motor_Only')
motor_parts=[]
for original in doc.Objects:
    if original.Name.lstrip('_').startswith(('01_cross_base','02_motor_pedestal','03_rim_shoe','04_tray_adapter',
                                  'Rim_shoe_copy','MG996R_','RB0051_','Pan_servo_M3_','Existing_tray')):
        o=motor_doc.addObject('Part::Feature',original.Name)
        o.Shape=original.Shape.copy();o.Label=original.Label
        if A.GuiUp:
            o.ViewObject.ShapeColor=original.ViewObject.ShapeColor
            o.ViewObject.Transparency=original.ViewObject.Transparency
        motor_parts.append(o)
motor_doc.recompute()
assert len(motor_parts)==16
Part.export(motor_parts,str(OUT/'motor_assembly.step'))
motor_doc.saveAs(str(OUT/'motor_assembly.FCStd'))
A.setActiveDocument(doc.Name)
if A.GuiUp:
    import FreeCADGui as Gui
    Gui.activeDocument().activeView().setCameraOrientation((0.424708,0.17592,0.339852,0.820473))
    Gui.activeDocument().activeView().fitAll()
print(json.dumps(checks,indent=2))
