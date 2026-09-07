from typing import Dict, Any, List, Optional
from shapely.geometry import Point, Polygon, LineString, MultiLineString, MultiPolygon, GeometryCollection, shape

def get_border_polygon(layers: Dict[str, Dict[str, Any]]) -> Optional[Polygon]:
    """Extract Shapely Polygon from the BORDER layer if available."""
    border_layer = layers.get("BORDER")
    if not border_layer:
        return None
    features = border_layer.get("features", [])
    if not features:
        return None
    coords = features[0].get("coords", [])
    if not coords:
        return None
    try:
        pts = coords[0] if (isinstance(coords[0], (list, tuple)) and len(coords[0]) > 0 and isinstance(coords[0][0], (list, tuple))) else coords
        poly = Polygon([(p[0], p[1]) for p in pts])
        if poly.is_valid and not poly.is_empty:
            return poly
    except Exception:
        pass
    return None

def clip_layers_to_border(
    layers: Dict[str, Dict[str, Any]],
    clip_polygon: Optional[Polygon] = None,
    skip_cadastral: bool = True
) -> Dict[str, Dict[str, Any]]:
    """Clip all layer features to a bounding polygon (e.g. circle or rectangle border).

    Cadastral layers ('HIGHLIGHT', 'CADASTRAL', 'LABEL', 'BORDER') are already clipped during generation,
    so by default they are preserved as-is.
    All topographic features (contours, roads, buildings, spot elevations) are neatly trimmed to clip_polygon.
    """
    if clip_polygon is None:
        clip_polygon = get_border_polygon(layers)
        
    if clip_polygon is None:
        return layers

    cadastral_keys = {"HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"}
    clipped_layers = {}

    for layer_id, l_data in layers.items():
        if skip_cadastral and layer_id in cadastral_keys:
            clipped_layers[layer_id] = l_data
            continue

        orig_features = l_data.get("features", [])
        clipped_features = []

        for feat in orig_features:
            f_type = feat.get("type")
            coords = feat.get("coords", [])
            elev = feat.get("elevation")
            text = feat.get("text")
            rec = feat.get("record", {})
            code = rec.get("code", l_data.get("code", ""))

            if not coords:
                continue

            # 1. Point / Label feature
            if f_type == "Point":
                pt_coords = coords[0] if isinstance(coords[0], (list, tuple)) else coords
                pt = Point(pt_coords[0], pt_coords[1])
                if clip_polygon.contains(pt):
                    clipped_features.append(feat)
                continue

            # 2. Linear feature (Contours F001, Roads A001, Streams C001, Retaining walls F004, Bridges, etc.)
            is_linear = (
                f_type in ("LineString", "MultiLineString")
                or code.startswith("F001")
                or code.startswith("A001")
                or code.startswith("A002")
                or code.startswith("A007")
                or code.startswith("F004")
                or code.startswith("C001")
                or code.startswith("D001")
            )

            if is_linear:
                lines = []
                if isinstance(coords[0], (list, tuple)) and len(coords[0]) > 0 and isinstance(coords[0][0], (list, tuple)):
                    for part in coords:
                        if len(part) >= 2:
                            lines.append(LineString([(p[0], p[1]) for p in part]))
                else:
                    if len(coords) >= 2:
                        lines.append(LineString([(p[0], p[1]) for p in coords]))

                if not lines:
                    continue

                geom = MultiLineString(lines) if len(lines) > 1 else lines[0]
                try:
                    inter = geom.intersection(clip_polygon)
                except Exception:
                    continue

                if inter.is_empty:
                    continue

                extracted_lines = []
                def _collect_lines(g):
                    if g.geom_type == "LineString" and len(g.coords) >= 2:
                        extracted_lines.append([[p[0], p[1]] for p in g.coords])
                    elif g.geom_type == "MultiLineString":
                        for part in g.geoms:
                            if len(part.coords) >= 2:
                                extracted_lines.append([[p[0], p[1]] for p in part.coords])
                    elif g.geom_type == "GeometryCollection":
                        for sub in g.geoms:
                            _collect_lines(sub)

                _collect_lines(inter)

                if extracted_lines:
                    clipped_features.append({
                        "type": "MultiLineString" if len(extracted_lines) > 1 else "LineString",
                        "coords": extracted_lines if len(extracted_lines) > 1 else extracted_lines[0],
                        "elevation": elev,
                        "text": text,
                        "record": rec
                    })

            # 3. Polygon feature (Buildings B001, Facilities, Cut/Fill F003, etc.)
            else:
                try:
                    p_coords = coords[0] if (isinstance(coords[0], (list, tuple)) and len(coords[0]) > 0 and isinstance(coords[0][0], (list, tuple))) else coords
                    poly = Polygon([(p[0], p[1]) for p in p_coords])
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    inter = poly.intersection(clip_polygon)
                except Exception:
                    continue

                if inter.is_empty:
                    continue

                extracted_polys = []
                def _collect_polys(g):
                    if g.geom_type == "Polygon" and len(g.exterior.coords) >= 3:
                        extracted_polys.append([[p[0], p[1]] for p in g.exterior.coords])
                    elif g.geom_type == "MultiPolygon":
                        for part in g.geoms:
                            if len(part.exterior.coords) >= 3:
                                extracted_polys.append([[p[0], p[1]] for p in part.exterior.coords])
                    elif g.geom_type == "GeometryCollection":
                        for sub in g.geoms:
                            _collect_polys(sub)

                _collect_polys(inter)

                if extracted_polys:
                    clipped_features.append({
                        "type": "MultiPolygon" if len(extracted_polys) > 1 else "Polygon",
                        "coords": extracted_polys if len(extracted_polys) > 1 else extracted_polys[0],
                        "elevation": elev,
                        "text": text,
                        "record": rec
                    })

        new_layer = dict(l_data)
        new_layer["features"] = clipped_features
        clipped_layers[layer_id] = new_layer

    return clipped_layers
