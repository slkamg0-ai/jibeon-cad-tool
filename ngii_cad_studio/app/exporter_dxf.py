from pathlib import Path
from typing import Dict, Any, List, Optional
import ezdxf
from ezdxf.enums import TextEntityAlignment
from .crs_converter import transform_coords

DEFAULT_FONT = "malgun.ttf"
TEXT_STYLE_NAME = "NGII_KOREAN"

def _extract_rings(coords: Any) -> List[List[Any]]:
    """Normalize polygon/multipolygon coords into a list of rings (each ring is a list of points)."""
    if not coords or not isinstance(coords, (list, tuple)):
        return []
    if isinstance(coords[0], (list, tuple)) and len(coords[0]) >= 2 and isinstance(coords[0][0], (int, float)):
        return [coords]
    if isinstance(coords[0], (list, tuple)) and len(coords[0]) > 0 and isinstance(coords[0][0], (list, tuple)):
        rings = []
        for part in coords:
            rings.extend(_extract_rings(part))
        return rings
    return []

def _extract_lines(coords: Any) -> List[List[Any]]:
    """Normalize linestring/multilinestring coords into a list of lines."""
    if not coords or not isinstance(coords, (list, tuple)):
        return []
    if isinstance(coords[0], (list, tuple)) and len(coords[0]) >= 2 and isinstance(coords[0][0], (int, float)):
        return [coords]
    if isinstance(coords[0], (list, tuple)) and len(coords[0]) > 0 and isinstance(coords[0][0], (list, tuple)):
        lines = []
        for part in coords:
            lines.extend(_extract_lines(part))
        return lines
    return []

def _draw_north_arrow(msp, x: float, y: float, size: float, text_style: Optional[str] = None):
    """Draw a clean surveyor's North Arrow pointing north (+Y)."""
    layer = "TITLE_BLOCK"
    msp.add_circle((x, y), radius=size, dxfattribs={"layer": layer, "color": 256})
    
    tip = (x, y + size * 1.35)
    left_base = (x - size * 0.45, y - size * 0.4)
    right_base = (x + size * 0.45, y - size * 0.4)
    center = (x, y)
    
    # Left half: Solid fill
    msp.add_solid([center, left_base, tip, tip], dxfattribs={"layer": layer, "color": 7})
    # Right half: Wireframe outline
    msp.add_lwpolyline([center, right_base, tip, center], dxfattribs={"layer": layer, "color": 256}, close=True)
    
    t_attr = {"layer": layer, "height": size * 0.55, "color": 256}
    if text_style:
        t_attr["style"] = text_style
    t = msp.add_text("N", dxfattribs=t_attr)
    t.set_placement((x, y + size * 1.55), align=TextEntityAlignment.BOTTOM_CENTER)

def _draw_scale_bar(msp, x: float, y: float, total_length: float, scale_label: str = "축척 1:1,000", text_style: Optional[str] = None):
    """Draw an alternating surveyor's meter scale bar."""
    layer = "TITLE_BLOCK"
    h = max(total_length * 0.045, 1.5)
    seg_len = total_length / 4.0
    
    # Outer frame
    msp.add_lwpolyline([(x, y), (x + total_length, y), (x + total_length, y + h), (x, y + h)], dxfattribs={"layer": layer, "color": 256}, close=True)
    
    # Alternating solid black blocks on 1st and 3rd sections
    for i in (0, 2):
        x1 = x + i * seg_len
        x2 = x + (i + 1) * seg_len
        msp.add_solid([(x1, y), (x2, y), (x1, y + h), (x2, y + h)], dxfattribs={"layer": layer, "color": 7})
        
    # Division tick lines
    for i in range(1, 4):
        xi = x + i * seg_len
        msp.add_line((xi, y), (xi, y + h * 1.4), dxfattribs={"layer": layer, "color": 256})
        
    # Numbers along the scale
    t_attr = {"layer": layer, "height": max(h * 1.1, 1.4), "color": 256}
    if text_style:
        t_attr["style"] = text_style
        
    for i, val in enumerate([0, int(seg_len), int(seg_len * 2), int(seg_len * 3), int(total_length)]):
        xi = x + i * seg_len
        lbl = f"{val}m" if i == 4 else str(val)
        t = msp.add_text(lbl, dxfattribs=t_attr)
        t.set_placement((xi, y + h * 1.6), align=TextEntityAlignment.BOTTOM_CENTER)
        
    # Ratio text below scale bar
    t_ratio = msp.add_text(scale_label, dxfattribs=t_attr)
    t_ratio.set_placement((x + total_length / 2.0, y - h * 1.5), align=TextEntityAlignment.TOP_CENTER)

def _draw_title_block(msp, x: float, y: float, width: float, height: float, metadata: Dict[str, Any], text_style: Optional[str] = None):
    """Draw a structured drawing title block table."""
    layer = "TITLE_BLOCK"
    msp.add_lwpolyline([(x, y), (x + width, y), (x + width, y + height), (x, y + height)], dxfattribs={"layer": layer, "color": 256}, close=True)
    
    rows = [
        ("도  면  명", metadata.get("title", "수치지형도 & 지적도 통합 현황도")),
        ("위      치", metadata.get("address", "도면 대상지 일대")),
        ("도  엽  명", metadata.get("topo_name", "-")),
        ("좌  표  계", metadata.get("crs", "GRS80 중부원점 (EPSG:5186)")),
        ("축척/도곽", f"{metadata.get('buffer_meters', 200)}m ({metadata.get('border_shape', '원형')} 도곽)"),
        ("작  성  일", metadata.get("date", "2026-09-07")),
        ("시  스  템", "NGII Map Studio CAD Engine")
    ]
    
    row_h = height / float(len(rows))
    label_w = width * 0.32
    
    # Vertical column line
    msp.add_line((x + label_w, y), (x + label_w, y + height), dxfattribs={"layer": layer, "color": 256})
    
    # Horizontal row lines
    for i in range(1, len(rows)):
        yi = y + i * row_h
        msp.add_line((x, yi), (x + width, yi), dxfattribs={"layer": layer, "color": 256})
        
    t_attr_label = {"layer": layer, "height": row_h * 0.45, "color": 256}
    t_attr_val = {"layer": layer, "height": row_h * 0.40, "color": 256}
    if text_style:
        t_attr_label["style"] = text_style
        t_attr_val["style"] = text_style
        
    for idx, (lbl, val) in enumerate(reversed(rows)):
        cy = y + (idx + 0.5) * row_h
        t1 = msp.add_text(lbl, dxfattribs=t_attr_label)
        t1.set_placement((x + label_w / 2.0, cy), align=TextEntityAlignment.MIDDLE_CENTER)
        
        val_str = str(val)
        if len(val_str) > 28:
            val_str = val_str[:26] + "..."
        t2 = msp.add_text(val_str, dxfattribs=t_attr_val)
        t2.set_placement((x + label_w + width * 0.03, cy), align=TextEntityAlignment.MIDDLE_LEFT)

def export_dxf(
    selected_layers: Dict[str, Dict[str, Any]],
    output_path: str,
    src_crs: str,
    target_crs: str = "SAME",
    unify_bylayer: bool = True,
    include_drawing_elements: bool = True,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Generate professional AutoCAD DXF with 3D elevation, ByLayer color unification,

    and optional drawing elements (North Arrow, Scale Bar, Title Block).
    """
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    
    # Register Korean font text style
    if TEXT_STYLE_NAME not in doc.styles:
        try:
            doc.styles.add(TEXT_STYLE_NAME, font=DEFAULT_FONT)
        except Exception:
            pass
            
    # Register Linetypes
    if "DASHED" not in doc.linetypes:
        try:
            doc.linetypes.add("DASHED", pattern=[0.5, 0.35, -0.15], description="Dashed __ __ __")
        except Exception:
            pass
    if "CENTER" not in doc.linetypes:
        try:
            doc.linetypes.add("CENTER", pattern=[1.0, 0.6, -0.15, 0.1, -0.15], description="Center ____ _ ____")
        except Exception:
            pass

    need_transform = (target_crs != "SAME" and target_crs != src_crs)
    entity_color = 256 if unify_bylayer else 7  # 256 = ByLayer
    
    # Create Title Block layer if needed (monochrome white/black, 0.25mm)
    if include_drawing_elements and "TITLE_BLOCK" not in doc.layers:
        doc.layers.add("TITLE_BLOCK", color=7, lineweight=25)
        
    # Track overall bounding box for placing North Arrow and Title Block
    min_gx = float("inf")
    min_gy = float("inf")
    max_gx = float("-inf")
    max_gy = float("-inf")
    
    def _update_bounds(pts):
        nonlocal min_gx, min_gy, max_gx, max_gy
        for p in pts:
            px, py = float(p[0]), float(p[1])
            min_gx = min(min_gx, px)
            min_gy = min(min_gy, py)
            max_gx = max(max_gx, px)
            max_gy = max(max_gy, py)
    
    for layer_id, l_data in selected_layers.items():
        major = l_data.get("major", "기타")
        mid = l_data.get("mid", "기타")
        code = l_data.get("code", layer_id)
        style = l_data.get("style", {})
        
        # Professional architectural drafting layer palette:
        # Grayscale background with clear distinguishability & lineweights
        ltype = "Continuous"
        if layer_id == "HIGHLIGHT":
            cad_layer_name = "HIGHLIGHT"
            dxf_color = 1  # Red (대지경계선 - 설계 대상 필지 가장 명확한 분별성)
            lw = 50       # 0.50mm (굵은 실선)
        elif layer_id == "CADASTRAL":
            cad_layer_name = "CADASTRAL"
            dxf_color = 8  # Dark Gray (차분한 인접 지적선)
            lw = 15       # 0.15mm (가는 실선)
        elif layer_id == "LABEL":
            cad_layer_name = "LABEL"
            dxf_color = 9  # Light Gray (가독성 높은 연한 지번 텍스트)
            lw = 15       # 0.15mm
        elif layer_id == "BORDER":
            cad_layer_name = "BORDER"
            dxf_color = 8  # Dark Gray
            lw = 25       # 0.25mm
            ltype = "DASHED" if "DASHED" in doc.linetypes else "Continuous"
        elif layer_id == "TITLE_BLOCK":
            cad_layer_name = "TITLE_BLOCK"
            dxf_color = 7  # White
            lw = 25       # 0.25mm
        else:
            cad_layer_name = f"{code}_{mid}".replace(" ", "_").replace("/", "_")
            # Distinguishable grayscale tones by code
            if code.startswith("F001"):
                # Contours
                if code == "F0017113":  # 주곡선 (Index contour 5m/10m)
                    dxf_color = 9       # Light Gray (식별 용이)
                    lw = 25             # 0.25mm
                else:                   # 계곡선/간곡선 (Minor contour)
                    dxf_color = 250     # Faint Gray (부드러운 등고 배경)
                    lw = 13             # 0.13mm
            elif code.startswith("B001"):
                # Existing Buildings
                dxf_color = 251         # Slate Gray (구조물 식별)
                lw = 25                 # 0.25mm
            elif code.startswith("A002"):
                # Road Centerline
                dxf_color = 8           # Dark Gray
                lw = 15                 # 0.15mm
                ltype = "CENTER" if "CENTER" in doc.linetypes else "Continuous"
            elif code.startswith("A001"):
                # Road Boundary
                dxf_color = 8           # Dark Gray
                lw = 20                 # 0.20mm
            elif code.startswith("C001") or code.startswith("E001"):
                # Water / Streams
                dxf_color = 251         # Slate Gray
                lw = 18                 # 0.18mm
            elif code.startswith("F002"):
                # Spot elevations
                dxf_color = 8           # Dark Gray
                lw = 13                 # 0.13mm
            else:
                dxf_color = style.get("dxf_color", 8)
                lw = 15
            
        if cad_layer_name not in doc.layers:
            doc.layers.add(cad_layer_name, color=dxf_color, lineweight=lw, linetype=ltype)
            
        features = l_data.get("features", [])
        for feat in features:
            f_type = feat.get("type", "LineString")
            coords = feat.get("coords", [])
            elev = feat.get("elevation")
            text = feat.get("text")
            
            if not coords:
                continue
                
            z_val = float(elev) if elev is not None else 0.0
            
            # --- Point & Label ---
            if f_type == "Point":
                pt = coords[0] if isinstance(coords[0], (list, tuple)) else coords
                if need_transform:
                    tx = transform_coords([(pt[0], pt[1])], src_crs, target_crs)
                    pt = tx[0]
                    
                _update_bounds([pt])
                
                if text:
                    t_height = 2.2 if layer_id == "LABEL" else 1.5
                    dxf_attr = {
                        "layer": cad_layer_name,
                        "height": t_height,
                        "color": entity_color,
                    }
                    if TEXT_STYLE_NAME in doc.styles:
                        dxf_attr["style"] = TEXT_STYLE_NAME
                    t_entity = msp.add_text(text, dxfattribs=dxf_attr)
                    t_entity.set_placement((pt[0], pt[1], z_val), align=TextEntityAlignment.MIDDLE_CENTER)
                else:
                    msp.add_point((pt[0], pt[1], z_val), dxfattribs={"layer": cad_layer_name, "color": entity_color})
                    if elev is not None and abs(elev) > 1e-4:
                        msp.add_text(f"{elev:.1f}", dxfattribs={"layer": cad_layer_name, "height": 1.5, "color": entity_color}).set_placement(
                            (pt[0] + 0.5, pt[1] + 0.5, z_val)
                        )
                        
            # --- Polygon & MultiPolygon ---
            elif f_type in ("Polygon", "MultiPolygon"):
                rings = _extract_rings(coords)
                for ring in rings:
                    if len(ring) < 3:
                        continue
                    if need_transform:
                        ring = transform_coords([(p[0], p[1]) for p in ring], src_crs, target_crs)
                        
                    _update_bounds(ring)
                    
                    if elev is not None and abs(elev) > 1e-4:
                        pts_3d = [(float(p[0]), float(p[1]), z_val) for p in ring]
                        poly3d = msp.add_polyline3d(pts_3d, dxfattribs={"layer": cad_layer_name, "color": entity_color})
                        poly3d.close(True)
                    else:
                        pts_2d = [(float(p[0]), float(p[1])) for p in ring]
                        msp.add_lwpolyline(pts_2d, dxfattribs={"layer": cad_layer_name, "elevation": z_val, "color": entity_color}, close=True)
                        
            # --- LineString & MultiLineString ---
            elif f_type in ("LineString", "MultiLineString"):
                lines = _extract_lines(coords)
                for line in lines:
                    if len(line) < 2:
                        continue
                    if need_transform:
                        line = transform_coords([(p[0], p[1]) for p in line], src_crs, target_crs)
                        
                    _update_bounds(line)
                    
                    is_closed = (line[0][0] == line[-1][0] and line[0][1] == line[-1][1])
                    if elev is not None and abs(elev) > 1e-4:
                        pts_3d = [(float(p[0]), float(p[1]), z_val) for p in line]
                        poly3d = msp.add_polyline3d(pts_3d, dxfattribs={"layer": cad_layer_name, "color": entity_color})
                        if is_closed:
                            poly3d.close(True)
                    else:
                        pts_2d = [(float(p[0]), float(p[1])) for p in line]
                        msp.add_lwpolyline(pts_2d, dxfattribs={"layer": cad_layer_name, "elevation": z_val, "color": entity_color}, close=is_closed)

    # --- Draw Professional Metadata Block (North Arrow, Scale Bar, Title Block) ---
    if include_drawing_elements and min_gx != float("inf"):
        span_x = max_gx - min_gx
        span_y = max_gy - min_gy
        radius = max(span_x, span_y) / 2.0
        cx = (min_gx + max_gx) / 2.0
        cy = (min_gy + max_gy) / 2.0
        
        meta = metadata or {}
        meta_dict = {
            "title": meta.get("title", "수치지형도 & 지적도 통합 현황도"),
            "address": meta.get("address", "도면 대상지 일대"),
            "topo_name": meta.get("topo_name", "-"),
            "crs": target_crs if target_crs != "SAME" else src_crs,
            "buffer_meters": f"{radius:.0f}" if radius > 0 else "200",
            "border_shape": meta.get("border_shape", "원형"),
            "date": meta.get("date", "2026-09-07")
        }
        
        txt_style = TEXT_STYLE_NAME if TEXT_STYLE_NAME in doc.styles else None
        
        # 1. North Arrow at top-right
        na_x = max_gx + radius * 0.08
        na_y = max_gy - radius * 0.05
        na_size = max(radius * 0.08, 8.0)
        _draw_north_arrow(msp, na_x, na_y, na_size, txt_style)
        
        # 2. Scale Bar at bottom-left
        sb_len = max(radius * 0.4, 20.0)
        # Round scale bar to nice number e.g. 50, 100, 200, 500
        if sb_len > 300:
            sb_len = 500.0
        elif sb_len > 150:
            sb_len = 200.0
        elif sb_len > 80:
            sb_len = 100.0
        elif sb_len > 40:
            sb_len = 50.0
        else:
            sb_len = 20.0
            
        sb_x = min_gx - radius * 0.05
        sb_y = min_gy - radius * 0.12
        _draw_scale_bar(msp, sb_x, sb_y, sb_len, f"축척 1:{int(sb_len * 10):,}", txt_style)
        
        # 3. Title Block at bottom-right
        tb_w = max(radius * 0.65, 80.0)
        tb_h = tb_w * 0.42
        tb_x = max_gx + radius * 0.05 - tb_w
        tb_y = min_gy - radius * 0.12 - tb_h
        _draw_title_block(msp, tb_x, tb_y, tb_w, tb_h, meta_dict, txt_style)

    doc.saveas(output_path)
    return output_path
