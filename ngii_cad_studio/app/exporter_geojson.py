import json
from pathlib import Path
from typing import Dict, Any, List
from .crs_converter import transform_coords

def _transform_point(pt, src_crs: str, out_crs: str, need_transform: bool) -> List[float]:
    if need_transform:
        tx = transform_coords([(pt[0], pt[1])], src_crs, out_crs)
        return [round(tx[0][0], 7), round(tx[0][1], 7)]
    return [round(pt[0], 7), round(pt[1], 7)]

def _transform_ring(ring, src_crs: str, out_crs: str, need_transform: bool) -> List[List[float]]:
    pts = [(p[0], p[1]) for p in ring]
    if need_transform:
        tx = transform_coords(pts, src_crs, out_crs)
        return [[round(p[0], 7), round(p[1], 7)] for p in tx]
    return [[round(p[0], 7), round(p[1], 7)] for p in pts]

def export_geojson(
    selected_layers: Dict[str, Dict[str, Any]],
    output_path: str,
    src_crs: str,
    target_crs: str = "EPSG:4326"
) -> str:
    """Generate standard GeoJSON FeatureCollection supporting all geometry types including MultiPolygon."""
    need_transform = (target_crs != "SAME" and target_crs != src_crs)
    out_crs = target_crs if target_crs != "SAME" else src_crs
    
    features = []
    
    for layer_id, l_data in selected_layers.items():
        major = l_data.get("major", "기타")
        mid = l_data.get("mid", "기타")
        minor = l_data.get("minor", layer_id)
        code = l_data.get("code", layer_id)
        style = l_data.get("style", {})
        
        for feat in l_data.get("features", []):
            f_type = feat.get("type", "LineString")
            raw_coords = feat.get("coords", [])
            elev = feat.get("elevation")
            text = feat.get("text")
            
            if not raw_coords:
                continue
                
            coords = None
            
            if f_type == "Point":
                pt = raw_coords[0] if isinstance(raw_coords[0], (list, tuple)) else raw_coords
                coords = _transform_point(pt, src_crs, out_crs, need_transform)
                
            elif f_type == "LineString":
                if len(raw_coords) >= 2:
                    coords = _transform_ring(raw_coords, src_crs, out_crs, need_transform)
                    
            elif f_type == "MultiLineString":
                lines = []
                for line in raw_coords:
                    if len(line) >= 2:
                        lines.append(_transform_ring(line, src_crs, out_crs, need_transform))
                if lines:
                    coords = lines
                    
            elif f_type == "Polygon":
                # GeoJSON Polygon: [ [ [x, y], ... ] ] (array of rings)
                if len(raw_coords) > 0 and isinstance(raw_coords[0], (list, tuple)) and len(raw_coords[0]) > 0 and isinstance(raw_coords[0][0], (list, tuple)):
                    rings = [_transform_ring(r, src_crs, out_crs, need_transform) for r in raw_coords if len(r) >= 3]
                    if rings:
                        coords = rings
                else:
                    if len(raw_coords) >= 3:
                        coords = [_transform_ring(raw_coords, src_crs, out_crs, need_transform)]
                        
            elif f_type == "MultiPolygon":
                # GeoJSON MultiPolygon: [ [ [ [x, y], ... ] ] ] (array of polygons, each an array of rings)
                polys = []
                for part in raw_coords:
                    if not part:
                        continue
                    if isinstance(part[0], (list, tuple)) and len(part[0]) > 0 and isinstance(part[0][0], (list, tuple)):
                        rings = [_transform_ring(r, src_crs, out_crs, need_transform) for r in part if len(r) >= 3]
                        if rings:
                            polys.append(rings)
                    else:
                        if len(part) >= 3:
                            polys.append([_transform_ring(part, src_crs, out_crs, need_transform)])
                if polys:
                    coords = polys

            if coords is None:
                continue
                
            props = {
                "layer": layer_id,
                "code": code,
                "major": major,
                "mid": mid,
                "minor": minor,
                "elevation": elev,
                "text": text,
                "color": style.get("color", "#4B5563")
            }
            if "record" in feat:
                props.update(feat["record"])
                
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": f_type,
                    "coordinates": coords
                },
                "properties": props
            })
            
    fc = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": out_crs}
        },
        "features": features
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
        
    return output_path
