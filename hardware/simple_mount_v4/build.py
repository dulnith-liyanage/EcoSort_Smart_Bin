"""Flat-faced motor support. Run normally for STL/preview; --step in FreeCAD Python for STEP."""
import sys,json
from pathlib import Path
R=Path(__file__).resolve().parent
native='--step' in sys.argv
if native:
    sys.path.append('/Applications/FreeCAD.app/Contents/Resources/lib')
    import FreeCAD as App, Part
    App.newDocument('SimpleMotorMount')
    def box(x,y,z,p):return Part.makeBox(x,y,z,App.Vector(*p))
    def join(a,b):return a.fuse(b)
    def cut(a,b):return a.cut(b)
else:
    import manifold3d, trimesh, numpy as np
    def box(x,y,z,p):return manifold3d.Manifold.cube((x,y,z)).translate(p)
    def mesh(s):
        m=s.to_mesh()
        return trimesh.Trimesh(vertices=np.asarray(m.vert_properties)[:,:3],faces=np.asarray(m.tri_verts),process=True)
    def join(a,b):return a+b
    def cut(a,b):return a-b
# Flat deck, hollow square tower, flat top: no decorative or curved surfaces.
s=box(160,160,8,(-80,-80,0))
s=join(s,box(60,60,100,(-30,-30,8)))
s=cut(s,box(48,48,101,(-24,-24,8)))
s=join(s,box(94,80,8,(-47,-40,108)))
s=cut(s,box(30,30,10,(-15,-15,107)))
# Front access window for the nuts securing the existing metal pan/tilt kit.
s=cut(s,box(30,8,30,(-15,-31,75)))
for x in [-30,30]:s=cut(s,box(4,24,10,(x-2,-12,107)))
for x in [-55,55]:
    for y in [-40,40]:s=cut(s,box(6,20,10,(x-3,y-10,-1)))
shoe=cut(box(28,35,8,(-14,-20,0)),box(6,6,10,(-3,-3,-1)))
if native:
    s.removeSplitter().exportStep(str(R/'motor_mount.step'))
    shoe.removeSplitter().exportStep(str(R/'optional_rim_shoe.step'))
else:
    report={}
    for name,solid,qty in [('motor_mount',s,1),('optional_rim_shoe',shoe,4)]:
        m=mesh(solid)
        assert m.is_watertight and m.is_winding_consistent and m.volume>0
        assert len(solid.decompose())==1
        m.export(R/(name+'.stl'))
        report[name]={'quantity':qty,'triangles':len(m.faces),'watertight':True,'single_body':True,'dimensions_mm':m.extents.tolist()}
    old=trimesh.load(R.parent/'motor_assembly_only/motor_mount_PRINT.stl')
    report['comparison']={'previous_mount_triangles':len(old.faces),'new_mount_triangles':len(mesh(s).faces)}
    (R/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
