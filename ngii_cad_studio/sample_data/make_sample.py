import os
from pathlib import Path
import ezdxf
import math

sample_dir = Path(__file__).parent
out_dxf = sample_dir / "37608044_2020_SAMPLE.dxf"

def create_sample_dxf():
    # Korea 2000 Central Belt EPSG:5186 coordinates (Pangyo/Seongnam area)
    base_x = 205500.0
    base_y = 533200.0
    
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    
    # Define layers with official NGII codes
    doc.layers.add("A0010000", color=8)   # 교통 > 도로경계
    doc.layers.add("A0020000", color=1)   # 교통 > 도로중심선
    doc.layers.add("B0010000", color=2)   # 건물 > 일반건물
    doc.layers.add("E0010001", color=5)   # 수계 > 하천경계
    doc.layers.add("F0017111", color=30)  # 지형 > 등고선(주곡선)
    doc.layers.add("F0017113", color=30)  # 지형 > 등고선(계곡선)
    doc.layers.add("F0027217", color=30)  # 지형 > 표고점
    doc.layers.add("F0040000", color=6)   # 시설/지형 > 옹벽
    doc.layers.add("G0010000", color=4)   # 경계 > 행정경계
    
    # 1. Road boundaries (A0010000)
    road_pts_left = [
        (base_x - 100, base_y - 200),
        (base_x - 50, base_y - 50),
        (base_x, base_y + 100),
        (base_x + 50, base_y + 250),
        (base_x + 100, base_y + 400)
    ]
    msp.add_lwpolyline(road_pts_left, dxfattribs={"layer": "A0010000"})
    
    road_pts_right = [(p[0] + 18, p[1]) for p in road_pts_left]
    msp.add_lwpolyline(road_pts_right, dxfattribs={"layer": "A0010000"})
    
    # 2. Road centerline (A0020000)
    road_center = [(p[0] + 9, p[1]) for p in road_pts_left]
    msp.add_lwpolyline(road_center, dxfattribs={"layer": "A0020000"})
    
    # 3. Buildings (B0010000)
    building_offsets = [
        (40, -100, 30, 20),
        (85, -80, 25, 25),
        (45, -20, 35, 20),
        (90, 10, 40, 30),
        (-80, -100, 25, 25),
        (-90, -40, 30, 20),
        (-70, 50, 25, 35),
        (70, 150, 45, 25),
    ]
    for ox, oy, w, h in building_offsets:
        bx = base_x + ox
        by = base_y + oy
        b_pts = [
            (bx, by),
            (bx + w, by),
            (bx + w, by + h),
            (bx, by + h),
            (bx, by)
        ]
        poly = msp.add_lwpolyline(b_pts, dxfattribs={"layer": "B0010000"})
        poly.close(True)
        
    # 4. River boundary (E0010001)
    river_pts_left = [
        (base_x + 180, base_y - 200),
        (base_x + 195, base_y - 50),
        (base_x + 210, base_y + 120),
        (base_x + 240, base_y + 350)
    ]
    river_pts_right = [(p[0] + 35, p[1]) for p in river_pts_left]
    msp.add_lwpolyline(river_pts_left, dxfattribs={"layer": "E0010001"})
    msp.add_lwpolyline(river_pts_right, dxfattribs={"layer": "E0010001"})
    
    # 5. 3D Contours (F0017111 - 주곡선, F0017113 - 계곡선)
    hill_cx = base_x - 120
    hill_cy = base_y + 220
    
    contours = [
        (40.0, 180.0, "F0017111"),
        (50.0, 150.0, "F0017113"), # 계곡선
        (60.0, 120.0, "F0017111"),
        (70.0, 95.0,  "F0017111"),
        (80.0, 70.0,  "F0017111"),
        (90.0, 48.0,  "F0017111"),
        (100.0, 25.0, "F0017113"), # 계곡선
    ]
    
    for elev, radius, l_code in contours:
        pts = []
        for deg in range(0, 365, 15):
            rad = math.radians(deg)
            wobble = 1.0 + 0.08 * math.sin(3 * rad) + 0.04 * math.cos(5 * rad)
            r = radius * wobble
            x = hill_cx + r * math.cos(rad)
            y = hill_cy + r * math.sin(rad)
            pts.append((x, y, elev))
            
        poly3d = msp.add_polyline3d(pts, dxfattribs={"layer": l_code})
        poly3d.close(True)
        
    # 6. Spot Elevation Points (F0027217)
    spot_points = [
        (hill_cx, hill_cy, 104.8),
        (hill_cx + 40, hill_cy - 30, 82.3),
        (base_x + 10, base_y - 80, 35.2),
        (base_x - 30, base_y + 40, 45.6)
    ]
    for px, py, pz in spot_points:
        msp.add_point((px, py, pz), dxfattribs={"layer": "F0027217"})
        msp.add_text(f"{pz:.1f}", dxfattribs={"layer": "F0027217", "height": 1.5}).set_placement(
            (px + 1.0, py + 1.0, pz)
        )
        
    # 7. Retaining Wall (F0040000 옹벽)
    wall_pts = [
        (base_x - 30, base_y + 120),
        (base_x - 25, base_y + 160),
        (base_x - 10, base_y + 200)
    ]
    msp.add_lwpolyline(wall_pts, dxfattribs={"layer": "F0040000"})
    
    # 8. Administrative Boundary (G0010000)
    admin_pts = [
        (base_x - 180, base_y - 220),
        (base_x - 100, base_y + 50),
        (base_x - 200, base_y + 350)
    ]
    msp.add_lwpolyline(admin_pts, dxfattribs={"layer": "G0010000"})
    
    doc.saveas(str(out_dxf))
    print(f"Sample DXF created successfully at: {out_dxf}")
    return str(out_dxf)

if __name__ == "__main__":
    create_sample_dxf()
