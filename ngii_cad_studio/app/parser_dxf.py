from pathlib import Path
from typing import Dict, Any, List, Optional
import ezdxf
from .codes import lookup_code
from .crs_converter import detect_crs_from_bounds, transform_coords

def parse_dxf(file_path: str, src_crs_override: Optional[str] = None) -> Dict[str, Any]:
    """Parse AutoCAD DXF file, extracting layer entities, standard codes, and 3D elevations."""
    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()
    
    layers_data: Dict[str, Dict[str, Any]] = {}
    
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")
    
    for entity in msp:
        layer_name = entity.dxf.layer.strip()
        dxftype = entity.dxftype()
        
        if layer_name not in layers_data:
            meta = lookup_code(layer_name)
            layers_data[layer_name] = {
                "layer_name": layer_name,
                "code": meta.get("code", layer_name),
                "major": meta.get("major", "기타"),
                "mid": meta.get("mid", "기타"),
                "minor": meta.get("minor", layer_name),
                "geom_type": meta.get("geom", ""),
                "style": meta.get("style", {}),
                "features": []
            }
            
        coords: List[List[float]] = []
        elevation: Optional[float] = None
        text_val: Optional[str] = None
        feat_type = "LineString"
        
        if dxftype == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            z = start.z if abs(start.z) > 1e-4 else (end.z if abs(end.z) > 1e-4 else None)
            elevation = z
            coords = [[start.x, start.y], [end.x, end.y]]
            feat_type = "LineString"
            
        elif dxftype == "LWPOLYLINE":
            elev = entity.dxf.elevation if entity.dxf.hasattr("elevation") else None
            elevation = elev if (elev is not None and abs(elev) > 1e-4) else None
            pts = entity.get_points(format="xy")
            coords = [[p[0], p[1]] for p in pts]
            if entity.is_closed and len(coords) > 2:
                feat_type = "Polygon"
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
            else:
                feat_type = "LineString"
                
        elif dxftype == "POLYLINE":
            elev = entity.dxf.elevation.z if entity.dxf.hasattr("elevation") else 0.0
            pts = []
            for v in entity.vertices:
                loc = v.dxf.location
                if abs(loc.z) > 1e-4 and elevation is None:
                    elevation = loc.z
                pts.append([loc.x, loc.y])
            if elevation is None and abs(elev) > 1e-4:
                elevation = elev
            coords = pts
            if entity.is_closed and len(coords) > 2:
                feat_type = "Polygon"
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
            else:
                feat_type = "LineString"
                
        elif dxftype == "POINT":
            loc = entity.dxf.location
            elevation = loc.z if abs(loc.z) > 1e-4 else None
            coords = [[loc.x, loc.y]]
            feat_type = "Point"
            
        elif dxftype in ("TEXT", "MTEXT"):
            loc = entity.dxf.insert
            elevation = loc.z if abs(loc.z) > 1e-4 else None
            text_val = entity.dxf.text if dxftype == "TEXT" else entity.plain_text()
            coords = [[loc.x, loc.y]]
            feat_type = "Point"
            
        elif dxftype == "CIRCLE":
            center = entity.dxf.center
            coords = [[center.x, center.y]]
            feat_type = "Point"
            
        if not coords:
            continue
            
        for pt in coords:
            min_x = min(min_x, pt[0])
            min_y = min(min_y, pt[1])
            max_x = max(max_x, pt[0])
            max_y = max(max_y, pt[1])
            
        layers_data[layer_name]["features"].append({
            "type": feat_type,
            "coords": coords,
            "elevation": elevation,
            "text": text_val,
            "entity_type": dxftype
        })

    # Detect coordinate system
    detected_crs = src_crs_override or detect_crs_from_bounds(min_x, min_y, max_x, max_y)
    
    # Calculate bounds in WGS84 for web map
    bounds_wgs84 = []
    if min_x != float("inf"):
        wgs_coords = transform_coords([(min_x, min_y), (max_x, max_y)], detected_crs, "EPSG:4326")
        bounds_wgs84 = [
            [wgs_coords[0][1], wgs_coords[0][0]], # [lat, lon]
            [wgs_coords[1][1], wgs_coords[1][0]]
        ]

    # Convert layer geometries to WGS84 for Leaflet preview
    layer_summaries = []
    for l_name, l_info in layers_data.items():
        feat_count = len(l_info["features"])
        if feat_count == 0:
            continue
            
        # Determine dominant geometry
        types = [f["type"] for f in l_info["features"]]
        geom_type = max(set(types), key=types.count)
        
        layer_summaries.append({
            "layer_name": l_name,
            "code": l_info["code"],
            "major": l_info["major"],
            "mid": l_info["mid"],
            "minor": l_info["minor"],
            "geom_type": geom_type,
            "feature_count": feat_count,
            "style": l_info["style"],
            "has_elevation": any(f["elevation"] is not None for f in l_info["features"])
        })
        
    return {
        "file_type": "DXF",
        "file_name": Path(file_path).name,
        "crs": detected_crs,
        "bounds_src": [min_x, min_y, max_x, max_y],
        "bounds_wgs84": bounds_wgs84,
        "layers": layers_data,
        "layer_summaries": layer_summaries
    }
