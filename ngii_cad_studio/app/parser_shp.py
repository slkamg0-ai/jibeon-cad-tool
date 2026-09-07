from pathlib import Path
from typing import Dict, Any, List, Optional
import shapefile
from .codes import lookup_code
from .crs_converter import detect_crs_from_prj, detect_crs_from_bounds, transform_coords

def parse_shp(file_path: str, src_crs_override: Optional[str] = None) -> Dict[str, Any]:
    """Parse ESRI Shapefile using pyshp, extracting geometry, attributes, and standard codes."""
    path_obj = Path(file_path)
    stem = path_obj.stem
    
    # Read PRJ if available
    prj_path = path_obj.with_suffix(".prj")
    detected_crs = src_crs_override
    if not detected_crs and prj_path.exists():
        detected_crs = detect_crs_from_prj(prj_path.read_text(encoding="utf-8", errors="ignore"))
        
    sf = shapefile.Reader(file_path, encoding="cp949")
    fields = [f[0] for f in sf.fields[1:]] # exclude DeletionFlag
    
    # Identify elevation and text/name fields
    elev_field = None
    for candidate in ("CONT_ELEV", "ELEV", "ALTI", "HEIGHT", "ELEVATION", "VAL"):
        if candidate in fields:
            elev_field = candidate
            break
            
    meta = lookup_code(stem)
    layer_name = stem
    
    min_x, min_y = sf.bbox[0], sf.bbox[1]
    max_x, max_y = sf.bbox[2], sf.bbox[3]
    
    if not detected_crs:
        detected_crs = detect_crs_from_bounds(min_x, min_y, max_x, max_y)
        
    features = []
    
    # Shape types: 1=Point, 3=PolyLine, 5=Polygon, 8=MultiPoint
    for shape_rec in sf.iterShapeRecords():
        shape = shape_rec.shape
        rec = shape_rec.record.as_dict()
        
        # Determine elevation
        elevation = None
        if elev_field and rec.get(elev_field) is not None:
            try:
                val = float(rec[elev_field])
                if abs(val) > 1e-4:
                    elevation = val
            except (ValueError, TypeError):
                pass
        elif hasattr(shape, "z") and shape.z:
            if abs(shape.z[0]) > 1e-4:
                elevation = float(shape.z[0])
                
        if shape.shapeType in (1, 8, 11, 21): # Point / MultiPoint
            pts = [[p[0], p[1]] for p in shape.points]
            feat_type = "Point" if len(pts) == 1 else "MultiPoint"
            coords = pts if len(pts) > 1 else pts[0]
        elif shape.shapeType in (3, 13, 23): # PolyLine
            # handle parts
            coords = []
            parts = list(shape.parts) + [len(shape.points)]
            for i in range(len(parts) - 1):
                part_pts = shape.points[parts[i]:parts[i+1]]
                coords.append([[p[0], p[1]] for p in part_pts])
            feat_type = "LineString" if len(coords) == 1 else "MultiLineString"
            coords = coords[0] if len(coords) == 1 else coords
        elif shape.shapeType in (5, 15, 25): # Polygon
            coords = []
            parts = list(shape.parts) + [len(shape.points)]
            for i in range(len(parts) - 1):
                part_pts = shape.points[parts[i]:parts[i+1]]
                coords.append([[p[0], p[1]] for p in part_pts])
            feat_type = "Polygon"
        else:
            continue
            
        features.append({
            "type": feat_type,
            "coords": coords,
            "elevation": elevation,
            "record": {k: str(v) for k, v in rec.items()}
        })

    # Bounds in WGS84
    wgs_coords = transform_coords([(min_x, min_y), (max_x, max_y)], detected_crs, "EPSG:4326")
    bounds_wgs84 = [
        [wgs_coords[0][1], wgs_coords[0][0]],
        [wgs_coords[1][1], wgs_coords[1][0]]
    ]
    
    types = [f["type"] for f in features]
    geom_type = max(set(types), key=types.count) if types else "Unknown"

    layer_dict = {
        layer_name: {
            "layer_name": layer_name,
            "code": meta.get("code", layer_name),
            "major": meta.get("major", "기타"),
            "mid": meta.get("mid", "기타"),
            "minor": meta.get("minor", layer_name),
            "geom_type": geom_type,
            "style": meta.get("style", {}),
            "features": features
        }
    }
    
    layer_summaries = [{
        "layer_name": layer_name,
        "code": meta.get("code", layer_name),
        "major": meta.get("major", "기타"),
        "mid": meta.get("mid", "기타"),
        "minor": meta.get("minor", layer_name),
        "geom_type": geom_type,
        "feature_count": len(features),
        "style": meta.get("style", {}),
        "has_elevation": any(f["elevation"] is not None for f in features)
    }]

    return {
        "file_type": "SHP",
        "file_name": path_obj.name,
        "crs": detected_crs,
        "bounds_src": [min_x, min_y, max_x, max_y],
        "bounds_wgs84": bounds_wgs84,
        "layers": layer_dict,
        "layer_summaries": layer_summaries
    }
