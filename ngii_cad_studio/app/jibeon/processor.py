from typing import Dict, Any, List, Optional, Tuple
from shapely.geometry import shape, Point, Polygon, MultiPolygon, box
from shapely.ops import clip_by_rect
from ..crs_converter import transform_coords
from .vworld_client import VWorldClient

def _format_jibun_label(props: Dict[str, Any]) -> str:
    # Check common VWorld property keys: jibun, pnu, bonbun, bubun, jimok
    jibun = props.get("jibun")
    if jibun:
        return str(jibun).strip()
    bon = props.get("bonbun")
    bu = props.get("bubun")
    jimok = props.get("jimok", "")
    if bon:
        label = f"{int(bon)}"
        if bu and int(bu) > 0:
            label += f"-{int(bu)}"
        if jimok:
            label += str(jimok)
        return label
    return props.get("pnu", "지번")[-4:]

def make_border_polygon(center_x: float, center_y: float, buffer_meters: float, shape_type: str = "rectangle") -> Polygon:
    if shape_type.lower() == "circle":
        return Point(center_x, center_y).buffer(buffer_meters, resolution=32)
    return box(center_x - buffer_meters, center_y - buffer_meters, center_x + buffer_meters, center_y + buffer_meters)

def process_cadastral(
    address: str,
    buffer_meters: float = 100.0,
    border_shape: str = "rectangle",
    vworld_client: Optional[VWorldClient] = None
) -> Dict[str, Any]:
    """Search address, download cadastral parcels, clip with buffer, and format for Web/CAD."""
    client = vworld_client or VWorldClient()
    search_res = client.search_parcel(address)
    
    cx, cy = search_res["x"], search_res["y"]
    pnu = search_res["pnu"]
    src_crs = search_res["crs"] # EPSG:5186
    
    # Download raw features from VWorld
    raw_features = client.download_cadastral(cx, cy, pnu, buffer_meters, crs=src_crs)
    
    clip_box = make_border_polygon(cx, cy, buffer_meters, border_shape)
    
    cadastral_features = []
    highlight_features = []
    label_features = []
    
    target_idx = None
    target_label = "지번"
    target_area_m2 = 0.0
    target_area_pyung = 0.0
    
    # 1. Identify target index
    for i, feat in enumerate(raw_features):
        feat_pnu = feat.get("properties", {}).get("pnu")
        if feat_pnu and feat_pnu == pnu:
            target_idx = i
            break
            
    if target_idx is None:
        cpoint = Point(cx, cy)
        for i, feat in enumerate(raw_features):
            poly = shape(feat["geometry"])
            if poly.contains(cpoint):
                target_idx = i
                break
        if target_idx is None and len(raw_features) > 0:
            target_idx = 0

    # 2. Process and clip polygons
    for idx, feat in enumerate(raw_features):
        props = feat.get("properties", {})
        label_text = _format_jibun_label(props)
        is_target = (idx == target_idx)
        if is_target:
            target_label = label_text
            
        geom = shape(feat["geometry"])
        try:
            clipped = geom.intersection(clip_box)
        except Exception:
            clipped = geom
            
        if clipped.is_empty:
            continue
            
        # Convert coords to list
        rings = []
        if clipped.geom_type == "Polygon":
            rings.append(list(clipped.exterior.coords))
        elif clipped.geom_type == "MultiPolygon":
            for part in clipped.geoms:
                rings.append(list(part.exterior.coords))
                
        feat_type = "MultiPolygon" if len(rings) > 1 else "Polygon"
        feat_coords = rings if len(rings) > 1 else (rings[0] if rings else [])
        
        # Calculate full parcel area in square meters and pyung
        area_m2 = round(geom.area, 1) if hasattr(geom, "area") else 0.0
        area_pyung = round(area_m2 / 3.305785, 1)
        if is_target:
            target_area_m2 = area_m2
            target_area_pyung = area_pyung

        feat_dict = {
            "type": feat_type,
            "coords": feat_coords,
            "elevation": 0.0,
            "record": {
                "PNU": props.get("pnu", ""),
                "JIBUN": label_text,
                "IS_TARGET": "Y" if is_target else "N",
                "AREA_M2": area_m2,
                "AREA_PYUNG": area_pyung
            }
        }
        
        if is_target:
            highlight_features.append(feat_dict)
        else:
            cadastral_features.append(feat_dict)
            
        # Label representative point
        try:
            rep_pt = clipped.representative_point()
            label_features.append({
                "type": "Point",
                "coords": [[rep_pt.x, rep_pt.y]],
                "elevation": 0.0,
                "text": label_text,
                "record": {
                    "JIBUN": label_text,
                    "IS_TARGET": "Y" if is_target else "N"
                }
            })
        except Exception:
            pass

    # 3. Border feature
    border_rings = list(clip_box.exterior.coords)
    border_features = [{
        "type": "Polygon",
        "coords": border_rings,
        "elevation": 0.0,
        "record": {"NAME": "BORDER"}
    }]

    # Package into layers dictionary matching NGII Map Studio layer format
    layers = {
        "HIGHLIGHT": {
            "layer_name": "HIGHLIGHT",
            "code": "HIGHLIGHT",
            "major": "경계",
            "mid": "대상필지",
            "minor": f"대상필지 ({target_label})",
            "geom_type": "Polygon",
            "style": {
                "color": "#EF4444",
                "fill_color": "#FCA5A5",
                "fill_opacity": 0.45,
                "weight": 3,
                "dxf_color": 1 # Red in CAD
            },
            "features": highlight_features
        },
        "CADASTRAL": {
            "layer_name": "CADASTRAL",
            "code": "CADASTRAL",
            "major": "경계",
            "mid": "인접지적선",
            "minor": "인접필지 지적경계",
            "geom_type": "Polygon",
            "style": {
                "color": "#64748B",
                "fill_color": "#334155",
                "fill_opacity": 0.05,
                "weight": 1.4,
                "dxf_color": 8 # Dark Gray in CAD (부드러운 인접 지적선)
            },
            "features": cadastral_features
        },
        "LABEL": {
            "layer_name": "LABEL",
            "code": "LABEL",
            "major": "주기",
            "mid": "지번주기",
            "minor": "지번 텍스트 라벨",
            "geom_type": "Point",
            "style": {
                "color": "#94A3B8",
                "fill_color": "#0F172A",
                "weight": 1.0,
                "dxf_color": 9 # Light Gray in CAD (가독성 높은 연한 지번 텍스트)
            },
            "features": label_features
        },
        "BORDER": {
            "layer_name": "BORDER",
            "code": "BORDER",
            "major": "경계",
            "mid": "도곽선",
            "minor": f"검색범위 ({buffer_meters}m 도곽)",
            "geom_type": "Polygon",
            "style": {
                "color": "#64748B",
                "fill_color": "transparent",
                "fill_opacity": 0.0,
                "weight": 1.5,
                "dash_array": "6, 4",
                "dxf_color": 8 # Dark Gray in CAD (가상 도곽선)
            },
            "features": border_features
        }
    }

    # Calculate WGS84 coordinates for Leaflet preview
    min_x = cx - buffer_meters
    min_y = cy - buffer_meters
    max_x = cx + buffer_meters
    max_y = cy + buffer_meters
    
    wgs_pts = transform_coords([(min_x, min_y), (max_x, max_y), (cx, cy)], src_crs, "EPSG:4326")
    bounds_wgs84 = [
        [wgs_pts[0][1], wgs_pts[0][0]],
        [wgs_pts[1][1], wgs_pts[1][0]]
    ]
    center_wgs84 = [wgs_pts[2][1], wgs_pts[2][0]]

    # Layer summaries
    layer_summaries = []
    for l_key, l_data in layers.items():
        layer_summaries.append({
            "layer_name": l_key,
            "code": l_data["code"],
            "major": l_data["major"],
            "mid": l_data["mid"],
            "minor": l_data["minor"],
            "geom_type": l_data["geom_type"],
            "feature_count": len(l_data["features"]),
            "style": l_data["style"],
            "has_elevation": False
        })

    return {
        "search_result": search_res,
        "target_pnu": pnu,
        "target_label": target_label,
        "target_area_m2": target_area_m2,
        "target_area_pyung": target_area_pyung,
        "crs": src_crs,
        "center_wgs84": center_wgs84,
        "bounds_wgs84": bounds_wgs84,
        "layers": layers,
        "layer_summaries": layer_summaries
    }

def fetch_cadastral_by_coords(
    center_x: float,
    center_y: float,
    buffer_meters: float = 200.0,
    border_shape: str = "rectangle",
    crs: str = "EPSG:5186",
    vworld_client: Optional[VWorldClient] = None
) -> Dict[str, Any]:
    """Fetch cadastral parcels directly around map center coordinates."""
    client = vworld_client or VWorldClient()
    raw_features = client.download_cadastral(center_x, center_y, "", buffer_meters, crs=crs)
    
    clip_box = make_border_polygon(center_x, center_y, buffer_meters, border_shape)
    
    cpoint = Point(center_x, center_y)
    target_idx = None
    for i, feat in enumerate(raw_features):
        poly = shape(feat["geometry"])
        if poly.contains(cpoint):
            target_idx = i
            break
            
    if target_idx is None and len(raw_features) > 0:
        target_idx = min(range(len(raw_features)), key=lambda i: shape(raw_features[i]["geometry"]).distance(cpoint))
        
    target_pnu = ""
    target_label = "지번"
    target_area_m2 = 0.0
    target_area_pyung = 0.0
    display_addr = ""
    if target_idx is not None and target_idx < len(raw_features):
        props = raw_features[target_idx].get("properties", {})
        target_pnu = props.get("pnu", "")
        display_addr = props.get("addr", "")
        
    if not display_addr and raw_features:
        display_addr = raw_features[0].get("properties", {}).get("addr", "")
    if not display_addr:
        display_addr = f"좌표 ({center_x:.0f}, {center_y:.0f}) 일대"

    cadastral_features = []
    highlight_features = []
    label_features = []
    
    for idx, feat in enumerate(raw_features):
        props = feat.get("properties", {})
        label_text = _format_jibun_label(props)
        is_target = (idx == target_idx)
        if is_target:
            target_label = label_text
            
        geom = shape(feat["geometry"])
        try:
            clipped = geom.intersection(clip_box)
        except Exception:
            clipped = geom
            
        if clipped.is_empty:
            continue
            
        rings = []
        if clipped.geom_type == "Polygon":
            rings.append(list(clipped.exterior.coords))
        elif clipped.geom_type == "MultiPolygon":
            for part in clipped.geoms:
                rings.append(list(part.exterior.coords))
                
        feat_type = "MultiPolygon" if len(rings) > 1 else "Polygon"
        feat_coords = rings if len(rings) > 1 else (rings[0] if rings else [])
        
        area_m2 = round(geom.area, 1) if hasattr(geom, "area") else 0.0
        area_pyung = round(area_m2 / 3.305785, 1)
        if is_target:
            target_area_m2 = area_m2
            target_area_pyung = area_pyung

        feat_dict = {
            "type": feat_type,
            "coords": feat_coords,
            "elevation": 0.0,
            "record": {
                "PNU": props.get("pnu", ""),
                "JIBUN": label_text,
                "IS_TARGET": "Y" if is_target else "N",
                "AREA_M2": area_m2,
                "AREA_PYUNG": area_pyung
            }
        }
        
        if is_target:
            highlight_features.append(feat_dict)
        else:
            cadastral_features.append(feat_dict)
            
        try:
            rep_pt = clipped.representative_point()
            label_features.append({
                "type": "Point",
                "coords": [[rep_pt.x, rep_pt.y]],
                "elevation": 0.0,
                "text": label_text,
                "record": {
                    "JIBUN": label_text,
                    "IS_TARGET": "Y" if is_target else "N"
                }
            })
        except Exception:
            pass

    border_rings = list(clip_box.exterior.coords)
    border_features = [{
        "type": "Polygon",
        "coords": border_rings,
        "elevation": 0.0,
        "record": {"NAME": "BORDER"}
    }]

    layers = {
        "HIGHLIGHT": {
            "layer_name": "HIGHLIGHT",
            "code": "HIGHLIGHT",
            "major": "경계",
            "mid": "대상필지",
            "minor": f"대상필지 ({target_label})",
            "geom_type": "Polygon",
            "style": {
                "color": "#EF4444",
                "fill_color": "#FCA5A5",
                "fill_opacity": 0.45,
                "weight": 3,
                "dxf_color": 1
            },
            "features": highlight_features
        },
        "CADASTRAL": {
            "layer_name": "CADASTRAL",
            "code": "CADASTRAL",
            "major": "경계",
            "mid": "인접지적선",
            "minor": "인접필지 지적경계",
            "geom_type": "Polygon",
            "style": {
                "color": "#64748B",
                "fill_color": "#334155",
                "fill_opacity": 0.05,
                "weight": 1.4,
                "dxf_color": 8
            },
            "features": cadastral_features
        },
        "LABEL": {
            "layer_name": "LABEL",
            "code": "LABEL",
            "major": "주기",
            "mid": "지번주기",
            "minor": "지번 텍스트 라벨",
            "geom_type": "Point",
            "style": {
                "color": "#94A3B8",
                "fill_color": "#0F172A",
                "weight": 1.0,
                "dxf_color": 9
            },
            "features": label_features
        },
        "BORDER": {
            "layer_name": "BORDER",
            "code": "BORDER",
            "major": "경계",
            "mid": "도곽선",
            "minor": f"검색범위 ({buffer_meters:.0f}m 도곽)",
            "geom_type": "Polygon",
            "style": {
                "color": "#64748B",
                "fill_color": "transparent",
                "fill_opacity": 0.0,
                "weight": 1.5,
                "dash_array": "6, 4",
                "dxf_color": 8
            },
            "features": border_features
        }
    }

    min_x = center_x - buffer_meters
    min_y = center_y - buffer_meters
    max_x = center_x + buffer_meters
    max_y = center_y + buffer_meters
    
    wgs_pts = transform_coords([(min_x, min_y), (max_x, max_y), (center_x, center_y)], crs, "EPSG:4326")
    bounds_wgs84 = [
        [wgs_pts[0][1], wgs_pts[0][0]],
        [wgs_pts[1][1], wgs_pts[1][0]]
    ]
    center_wgs84 = [wgs_pts[2][1], wgs_pts[2][0]]

    layer_summaries = []
    for l_key, l_data in layers.items():
        layer_summaries.append({
            "layer_name": l_key,
            "code": l_data["code"],
            "major": l_data["major"],
            "mid": l_data["mid"],
            "minor": l_data["minor"],
            "geom_type": l_data["geom_type"],
            "feature_count": len(l_data["features"]),
            "style": l_data["style"],
            "has_elevation": False
        })

    return {
        "search_result": {
            "address": display_addr,
            "pnu": target_pnu,
            "x": center_x,
            "y": center_y,
            "crs": crs
        },
        "target_pnu": target_pnu,
        "target_label": target_label,
        "target_area_m2": target_area_m2,
        "target_area_pyung": target_area_pyung,
        "crs": crs,
        "center_wgs84": center_wgs84,
        "bounds_wgs84": bounds_wgs84,
        "layers": layers,
        "layer_summaries": layer_summaries
    }

