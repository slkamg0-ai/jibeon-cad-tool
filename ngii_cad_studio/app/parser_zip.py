import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from .parser_dxf import parse_dxf
from .parser_shp import parse_shp
from .codes import lookup_code
from .crs_converter import detect_crs_from_bounds, transform_coords

def extract_zip_recursive(zip_path: str, extract_to: Path):
    """Recursively unpack zip files (handles nested zips from NGII)."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Check encoding for Korean filenames (cp949 vs utf-8)
        for member in zf.infolist():
            try:
                # Try cp949 decoding if needed
                filename = member.filename.encode('cp437').decode('cp949')
            except Exception:
                filename = member.filename
            target_path = extract_to / filename
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                    
    # Find nested zips and extract them
    for nested_zip in list(extract_to.rglob("*.zip")):
        nested_dir = nested_zip.parent / nested_zip.stem
        nested_dir.mkdir(parents=True, exist_ok=True)
        try:
            extract_zip_recursive(str(nested_zip), nested_dir)
            nested_zip.unlink() # remove nested archive once unpacked
        except Exception:
            pass

def parse_zip(zip_path: str, src_crs_override: Optional[str] = None) -> Dict[str, Any]:
    """Extract and parse all DXF/SHP files inside a ZIP archive, merging layers by standard code."""
    temp_dir = Path(tempfile.mkdtemp(prefix="ngii_extract_"))
    try:
        extract_zip_recursive(zip_path, temp_dir)
        
        # 1. Look for DXF files
        dxf_files = list(temp_dir.rglob("*.dxf")) + list(temp_dir.rglob("*.DXF"))
        # 2. Look for SHP files
        shp_files = list(temp_dir.rglob("*.shp")) + list(temp_dir.rglob("*.SHP"))
        
        merged_layers: Dict[str, Dict[str, Any]] = {}
        all_crs_list = []
        overall_min_x, overall_min_y = float("inf"), float("inf")
        overall_max_x, overall_max_y = float("-inf"), float("-inf")
        
        # Process DXFs
        for df in dxf_files:
            try:
                res = parse_dxf(str(df), src_crs_override)
                all_crs_list.append(res["crs"])
                b_src = res["bounds_src"]
                overall_min_x = min(overall_min_x, b_src[0])
                overall_min_y = min(overall_min_y, b_src[1])
                overall_max_x = max(overall_max_x, b_src[2])
                overall_max_y = max(overall_max_y, b_src[3])
                
                for l_name, l_data in res["layers"].items():
                    key = l_data["code"] or l_name
                    if key not in merged_layers:
                        merged_layers[key] = l_data
                    else:
                        merged_layers[key]["features"].extend(l_data["features"])
            except Exception as e:
                print(f"Error parsing DXF {df.name}: {e}")
                
        # Process SHPs
        for sf in shp_files:
            try:
                res = parse_shp(str(sf), src_crs_override)
                all_crs_list.append(res["crs"])
                b_src = res["bounds_src"]
                overall_min_x = min(overall_min_x, b_src[0])
                overall_min_y = min(overall_min_y, b_src[1])
                overall_max_x = max(overall_max_x, b_src[2])
                overall_max_y = max(overall_max_y, b_src[3])
                
                for l_name, l_data in res["layers"].items():
                    key = l_data["code"] or l_name
                    if key not in merged_layers:
                        merged_layers[key] = l_data
                    else:
                        merged_layers[key]["features"].extend(l_data["features"])
            except Exception as e:
                print(f"Error parsing SHP {sf.name}: {e}")
                
        primary_crs = src_crs_override or (all_crs_list[0] if all_crs_list else "EPSG:5186")
        
        bounds_wgs84 = []
        if overall_min_x != float("inf"):
            wgs_coords = transform_coords([(overall_min_x, overall_min_y), (overall_max_x, overall_max_y)], primary_crs, "EPSG:4326")
            bounds_wgs84 = [
                [wgs_coords[0][1], wgs_coords[0][0]],
                [wgs_coords[1][1], wgs_coords[1][0]]
            ]
            
        layer_summaries = []
        for l_key, l_data in merged_layers.items():
            feat_count = len(l_data["features"])
            if feat_count == 0:
                continue
            types = [f["type"] for f in l_data["features"]]
            geom_type = max(set(types), key=types.count) if types else "Unknown"
            
            layer_summaries.append({
                "layer_name": l_key,
                "code": l_data["code"],
                "major": l_data["major"],
                "mid": l_data["mid"],
                "minor": l_data["minor"],
                "geom_type": geom_type,
                "feature_count": feat_count,
                "style": l_data["style"],
                "has_elevation": any(f.get("elevation") is not None for f in l_data["features"])
            })
            
        return {
            "file_type": "ZIP",
            "file_name": Path(zip_path).name,
            "crs": primary_crs,
            "bounds_src": [overall_min_x, overall_min_y, overall_max_x, overall_max_y],
            "bounds_wgs84": bounds_wgs84,
            "layers": merged_layers,
            "layer_summaries": layer_summaries
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
