import os
import re
import shutil
import tempfile
import uuid
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import ENCODERS_BY_TYPE
from pydantic import BaseModel
import numpy as np

# Prevent numpy types (np.bool_, np.floating, etc.) from breaking FastAPI JSON serialization
ENCODERS_BY_TYPE[np.bool_] = bool
ENCODERS_BY_TYPE[np.integer] = int
ENCODERS_BY_TYPE[np.floating] = float
ENCODERS_BY_TYPE[np.ndarray] = lambda x: x.tolist()

from .codes import lookup_code, get_taxonomy_tree, get_presets, CATEGORY_DEFAULTS
from .crs_converter import SUPPORTED_CRS, transform_coords
from .parser_dxf import parse_dxf
from .parser_shp import parse_shp
from .parser_zip import parse_zip
from .exporter_dxf import export_dxf
from .exporter_geojson import export_geojson
from .exporter_shp import export_shp_zip
from .jibeon.processor import process_cadastral, fetch_cadastral_by_coords
from .clipper import clip_layers_to_border, get_border_polygon
from .topo_generator import generate_topo_layers_for_parcel

app = FastAPI(title="NGII Map Studio", description="국토정보플랫폼 수치지형도 & VWorld 지적도 통합 CAD 추출기")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Suggested-Filename"],
)

# In-memory session store
# session_id -> { "file_name": str, "crs": str, "layers": dict, "bounds_wgs84": list, "bounds_src": list }
SESSIONS: Dict[str, Dict[str, Any]] = {}

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

class ExportRequest(BaseModel):
    session_id: str
    selected_layers: List[str]
    format: str # dxf, geojson, shp, html
    target_crs: str = "SAME" # SAME, EPSG:5186, EPSG:5179, EPSG:4326
    clip_to_border: bool = True
    unify_bylayer: bool = True
    include_drawing_elements: bool = True

class PreviewRequest(BaseModel):
    session_id: str
    selected_layers: List[str]
    clip_to_border: bool = True

class JibeonRequest(BaseModel):
    address: str
    buffer_meters: float = 100.0
    border_shape: str = "rectangle" # rectangle or circle
    session_id: Optional[str] = None

class MapCenterJibeonRequest(BaseModel):
    session_id: str
    buffer_meters: float = 200.0
    border_shape: str = "rectangle"

class GpsJibeonRequest(BaseModel):
    latitude: float
    longitude: float
    buffer_meters: float = 100.0
    border_shape: str = "rectangle"
    session_id: Optional[str] = None

class TopoGenerateRequest(BaseModel):
    session_id: str
    buffer_meters: Optional[float] = None
    border_shape: Optional[str] = None

@app.get("/api/crs-list")
def get_crs_list():
    return SUPPORTED_CRS

@app.get("/api/presets")
def get_presets_api():
    return get_presets()

@app.get("/api/taxonomy")
def get_taxonomy_api():
    return get_taxonomy_tree()

@app.get("/api/sample")
def get_sample_file():
    """Serve realistic pre-generated sample topographic DXF."""
    sample_file = Path(__file__).parent.parent / "sample_data" / "37608044_2020_SAMPLE.dxf"
    if not sample_file.exists():
        from ..sample_data.make_sample import create_sample_dxf
        create_sample_dxf()
    return FileResponse(
        str(sample_file),
        filename="37608044_2020_SAMPLE.dxf",
        media_type="application/dxf"
    )

@app.post("/api/upload")
async def upload_file(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    crs_override: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """Handle upload of one or multiple .zip, .dxf, or .shp files and merge them seamlessly."""
    all_uploads: List[UploadFile] = []
    if files:
        all_uploads.extend(files)
    if file and file not in all_uploads:
        all_uploads.append(file)
        
    if not all_uploads:
        raise HTTPException(status_code=400, detail="업로드할 도면 파일이 없습니다.")
        
    temp_dir = Path(tempfile.mkdtemp(prefix="ngii_upload_"))
    try:
        combined_layers: Dict[str, Dict[str, Any]] = {}
        all_bounds_src = [float("inf"), float("inf"), float("-inf"), float("-inf")]
        valid_filenames: List[str] = []
        detected_crs = crs_override or None
        
        for up_file in all_uploads:
            suffix = Path(up_file.filename).suffix.lower()
            if suffix not in (".zip", ".dxf", ".shp"):
                continue
                
            valid_filenames.append(up_file.filename)
            temp_file = temp_dir / up_file.filename
            with open(temp_file, "wb") as f:
                shutil.copyfileobj(up_file.file, f)
                
            if suffix == ".zip":
                parsed = parse_zip(str(temp_file), crs_override)
            elif suffix == ".dxf":
                parsed = parse_dxf(str(temp_file), crs_override)
            elif suffix == ".shp":
                parsed = parse_shp(str(temp_file), crs_override)
                
            if not detected_crs:
                detected_crs = parsed.get("crs", "EPSG:5186")
                
            b = parsed.get("bounds_src", [0, 0, 0, 0])
            if b and len(b) == 4 and (b[0] != 0 or b[1] != 0):
                all_bounds_src[0] = min(all_bounds_src[0], b[0])
                all_bounds_src[1] = min(all_bounds_src[1], b[1])
                all_bounds_src[2] = max(all_bounds_src[2], b[2])
                all_bounds_src[3] = max(all_bounds_src[3], b[3])
                
            for l_key, l_data in parsed.get("layers", {}).items():
                if l_key not in combined_layers:
                    combined_layers[l_key] = dict(l_data)
                    combined_layers[l_key]["features"] = list(l_data.get("features", []))
                else:
                    combined_layers[l_key]["features"].extend(l_data.get("features", []))

        if not combined_layers:
            raise HTTPException(status_code=400, detail="유효한 수치지형도 레이어를 찾을 수 없습니다.")

        existing_cadastral = {}
        if session_id and session_id in SESSIONS:
            old_sess = SESSIONS[session_id]
            for k in ("HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"):
                if k in old_sess.get("layers", {}):
                    existing_cadastral[k] = old_sess["layers"][k]
                    
        sess_id = session_id if (session_id and session_id in SESSIONS) else str(uuid.uuid4())
        
        merged_layers = dict(combined_layers)
        merged_layers.update(existing_cadastral)
        
        if all_bounds_src[0] == float("inf"):
            all_bounds_src = [0, 0, 0, 0]
            center_x, center_y = 0.0, 0.0
            center_wgs84 = [37.5665, 126.9780]
            bounds_wgs84 = []
        else:
            center_x = (all_bounds_src[0] + all_bounds_src[2]) / 2.0
            center_y = (all_bounds_src[1] + all_bounds_src[3]) / 2.0
            pts_wgs = transform_coords([
                (all_bounds_src[0], all_bounds_src[1]),
                (all_bounds_src[2], all_bounds_src[3]),
                (center_x, center_y)
            ], detected_crs, "EPSG:4326")
            bounds_wgs84 = [
                [pts_wgs[0][1], pts_wgs[0][0]],
                [pts_wgs[1][1], pts_wgs[1][0]]
            ]
            center_wgs84 = [pts_wgs[2][1], pts_wgs[2][0]]
        
        display_filename = ", ".join(valid_filenames) if len(valid_filenames) <= 2 else f"{valid_filenames[0]} 외 {len(valid_filenames)-1}건"
        
        prev_session = SESSIONS.get(sess_id, {})
        existing_address = prev_session.get("address")
        existing_buffer = prev_session.get("buffer_meters", 200.0)
        existing_shape = prev_session.get("border_shape", "rectangle")
        
        detected_address = existing_address or ""
        if not detected_address and center_x and center_y:
            try:
                detected_data = fetch_cadastral_by_coords(center_x, center_y, buffer_meters=150.0, crs=detected_crs)
                detected_address = detected_data.get("search_result", {}).get("address", "")
            except Exception:
                pass

        SESSIONS[sess_id] = {
            "file_name": display_filename,
            "crs": detected_crs,
            "layers": merged_layers,
            "bounds_wgs84": bounds_wgs84,
            "bounds_src": all_bounds_src,
            "center_coords": [center_x, center_y],
            "center_wgs84": center_wgs84,
            "address": detected_address,
            "buffer_meters": existing_buffer,
            "border_shape": existing_shape
        }
            
        all_summaries = []
        for l_key, l_data in merged_layers.items():
            all_summaries.append({
                "layer_name": l_key,
                "code": l_data.get("code", l_key),
                "major": l_data.get("major", "기타"),
                "mid": l_data.get("mid", "기타"),
                "minor": l_data.get("minor", l_key),
                "geom_type": l_data.get("geom_type", "Polygon"),
                "feature_count": len(l_data.get("features", [])),
                "style": l_data.get("style", {}),
                "has_elevation": any(f.get("elevation") is not None and abs(f.get("elevation", 0)) > 1e-4 for f in l_data.get("features", []))
            })
            
        return {
            "session_id": sess_id,
            "file_name": display_filename,
            "crs": detected_crs,
            "bounds_wgs84": bounds_wgs84,
            "bounds_src": all_bounds_src,
            "center_coords": [center_x, center_y],
            "center_wgs84": center_wgs84,
            "detected_address": detected_address,
            "cadastral_layer_keys": list(existing_cadastral.keys()),
            "layer_summaries": all_summaries
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/jibeon/fetch")
def fetch_cadastral(req: JibeonRequest):
    """Fetch cadastral parcels and labels from VWorld API, integrating with current session."""
    try:
        jibeon_data = process_cadastral(
            address=req.address,
            buffer_meters=req.buffer_meters,
            border_shape=req.border_shape
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    session_id = req.session_id
    jx = float(jibeon_data["search_result"]["x"])
    jy = float(jibeon_data["search_result"]["y"])
    buf = float(req.buffer_meters)

    if not session_id or session_id not in SESSIONS:
        # Create standalone cadastral session
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {
            "file_name": f"{req.address}_지적도.dxf",
            "crs": jibeon_data["crs"],
            "layers": jibeon_data["layers"],
            "bounds_wgs84": jibeon_data["bounds_wgs84"],
            "bounds_src": [jx - buf, jy - buf, jx + buf, jy + buf],
            "center_coords": [jx, jy],
            "center_wgs84": jibeon_data["center_wgs84"],
            "address": jibeon_data["search_result"]["address"],
            "buffer_meters": req.buffer_meters,
            "border_shape": req.border_shape
        }
    else:
        # Merge cadastral layers into existing topographic session!
        sess = SESSIONS[session_id]
        sess["layers"].update(jibeon_data["layers"])
        sess["bounds_wgs84"] = jibeon_data["bounds_wgs84"]
        sess["center_coords"] = [jx, jy]
        sess["center_wgs84"] = jibeon_data["center_wgs84"]
        if sess.get("bounds_src") == [0, 0, 0, 0]:
            sess["bounds_src"] = [jx - buf, jy - buf, jx + buf, jy + buf]
        sess["address"] = jibeon_data["search_result"]["address"]
        sess["buffer_meters"] = req.buffer_meters
        sess["border_shape"] = req.border_shape
        
    distance_info = None
    if session_id in SESSIONS:
        sess = SESSIONS[session_id]
        b_src = sess.get("bounds_src")
        if b_src and len(b_src) == 4 and (b_src[0] != 0 or b_src[1] != 0):
            cx = (float(b_src[0]) + float(b_src[2])) / 2.0
            cy = (float(b_src[1]) + float(b_src[3])) / 2.0
            jx = float(jibeon_data["search_result"]["x"])
            jy = float(jibeon_data["search_result"]["y"])
            dist_m = float(((jx - cx)**2 + (jy - cy)**2)**0.5)
            is_inside = bool(b_src[0] <= jx <= b_src[2] and b_src[1] <= jy <= b_src[3])
            distance_info = {
                "distance_meters": float(round(dist_m, 1)),
                "distance_km": float(round(dist_m / 1000.0, 2)),
                "is_inside_topo": bool(is_inside),
                "is_far": bool(dist_m > 3000.0)
            }
        
    # Return all layer summaries for the session
    all_summaries = []
    for l_key, l_data in SESSIONS[session_id]["layers"].items():
        all_summaries.append({
            "layer_name": str(l_key),
            "code": str(l_data.get("code", l_key)),
            "major": str(l_data.get("major", "기타")),
            "mid": str(l_data.get("mid", "기타")),
            "minor": str(l_data.get("minor", l_key)),
            "geom_type": str(l_data.get("geom_type", "Polygon")),
            "feature_count": int(len(l_data.get("features", []))),
            "style": l_data.get("style", {}),
            "has_elevation": bool(any(f.get("elevation") is not None and abs(f.get("elevation", 0)) > 1e-4 for f in l_data.get("features", [])))
        })
        
    return {
        "session_id": str(session_id),
        "address": str(jibeon_data["search_result"]["address"]),
        "target_pnu": str(jibeon_data["target_pnu"]),
        "target_label": str(jibeon_data["target_label"]),
        "target_area_m2": float(jibeon_data.get("target_area_m2", 0.0)),
        "target_area_pyung": float(jibeon_data.get("target_area_pyung", 0.0)),
        "center_wgs84": [float(c) for c in jibeon_data["center_wgs84"]],
        "bounds_wgs84": [[float(c) for c in b] for b in jibeon_data["bounds_wgs84"]],
        "cadastral_layer_keys": list(jibeon_data["layers"].keys()),
        "distance_info": distance_info,
        "layer_summaries": all_summaries
    }

@app.post("/api/jibeon/fetch-by-map-center")
def fetch_by_map_center(req: MapCenterJibeonRequest):
    """Fetch cadastral parcels directly centered on the uploaded topographic map bounds."""
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다. 도면을 먼저 업로드해 주세요.")
    bounds_src = session.get("bounds_src")
    if not bounds_src or len(bounds_src) != 4 or (bounds_src[0] == 0 and bounds_src[1] == 0):
        raise HTTPException(status_code=400, detail="업로드된 수치지형도의 유효한 좌표 범위를 찾을 수 없습니다.")
        
    cx = (bounds_src[0] + bounds_src[2]) / 2.0
    cy = (bounds_src[1] + bounds_src[3]) / 2.0
    crs = session.get("crs", "EPSG:5186")
    
    try:
        jibeon_data = fetch_cadastral_by_coords(
            center_x=cx,
            center_y=cy,
            buffer_meters=req.buffer_meters,
            border_shape=req.border_shape,
            crs=crs
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    session["layers"].update(jibeon_data["layers"])
    session["address"] = jibeon_data["search_result"]["address"]
    session["buffer_meters"] = req.buffer_meters
    session["border_shape"] = req.border_shape
    
    all_summaries = []
    for l_key, l_data in session["layers"].items():
        all_summaries.append({
            "layer_name": str(l_key),
            "code": str(l_data.get("code", l_key)),
            "major": str(l_data.get("major", "기타")),
            "mid": str(l_data.get("mid", "기타")),
            "minor": str(l_data.get("minor", l_key)),
            "geom_type": str(l_data.get("geom_type", "Polygon")),
            "feature_count": int(len(l_data.get("features", []))),
            "style": l_data.get("style", {}),
            "has_elevation": bool(any(f.get("elevation") is not None and abs(f.get("elevation", 0)) > 1e-4 for f in l_data.get("features", [])))
        })
        
    return {
        "session_id": str(req.session_id),
        "address": str(jibeon_data["search_result"]["address"]),
        "target_pnu": str(jibeon_data["target_pnu"]),
        "target_label": str(jibeon_data["target_label"]),
        "target_area_m2": float(jibeon_data.get("target_area_m2", 0.0)),
        "target_area_pyung": float(jibeon_data.get("target_area_pyung", 0.0)),
        "center_wgs84": [float(c) for c in jibeon_data["center_wgs84"]],
        "bounds_wgs84": [[float(c) for c in b] for b in jibeon_data["bounds_wgs84"]],
        "cadastral_layer_keys": list(jibeon_data["layers"].keys()),
        "layer_summaries": all_summaries
    }

@app.post("/api/jibeon/fetch-by-gps")
def fetch_by_gps(req: GpsJibeonRequest):
    """Fetch cadastral parcels directly from smartphone/field GPS coordinates."""
    coords_5186 = transform_coords([(req.longitude, req.latitude)], "EPSG:4326", "EPSG:5186")
    cx, cy = coords_5186[0]
    
    try:
        jibeon_data = fetch_cadastral_by_coords(
            center_x=cx,
            center_y=cy,
            buffer_meters=req.buffer_meters,
            border_shape=req.border_shape,
            crs="EPSG:5186"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"현장 GPS 위치 지적도 수집 실패: {e}")
        
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "file_name": "GPS_현장도면",
            "crs": "EPSG:5186",
            "layers": {},
            "bounds_wgs84": jibeon_data["bounds_wgs84"],
            "bounds_src": [cx - req.buffer_meters, cy - req.buffer_meters, cx + req.buffer_meters, cy + req.buffer_meters]
        }
        
    session = SESSIONS[session_id]
    session["layers"].update(jibeon_data["layers"])
    session["address"] = jibeon_data["search_result"]["address"]
    session["buffer_meters"] = req.buffer_meters
    session["border_shape"] = req.border_shape
    
    all_summaries = []
    for l_key, l_data in session["layers"].items():
        all_summaries.append({
            "layer_name": str(l_key),
            "code": str(l_data.get("code", l_key)),
            "major": str(l_data.get("major", "기타")),
            "mid": str(l_data.get("mid", "기타")),
            "minor": str(l_data.get("minor", l_key)),
            "geom_type": str(l_data.get("geom_type", "Polygon")),
            "feature_count": int(len(l_data.get("features", []))),
            "style": l_data.get("style", {}),
            "has_elevation": bool(any(f.get("elevation") is not None and abs(f.get("elevation", 0)) > 1e-4 for f in l_data.get("features", [])))
        })
        
    return {
        "session_id": str(session_id),
        "address": str(jibeon_data["search_result"]["address"]),
        "target_pnu": str(jibeon_data["target_pnu"]),
        "target_label": str(jibeon_data["target_label"]),
        "target_area_m2": float(jibeon_data.get("target_area_m2", 0.0)),
        "target_area_pyung": float(jibeon_data.get("target_area_pyung", 0.0)),
        "center_wgs84": [float(c) for c in jibeon_data["center_wgs84"]],
        "bounds_wgs84": [[float(c) for c in b] for b in jibeon_data["bounds_wgs84"]],
        "cadastral_layer_keys": list(jibeon_data["layers"].keys()),
        "layer_summaries": all_summaries
    }

@app.post("/api/topo/generate-for-current-parcel")
def generate_topo_for_current_parcel(req: TopoGenerateRequest):
    """Dynamically generate 3D contour lines and spot elevations centered on current searched parcel."""
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다. 지번이나 주소를 먼저 검색해 주세요.")
        
    center = session.get("center_coords")
    crs = session.get("crs", "EPSG:5186")
    buf = float(req.buffer_meters or session.get("buffer_meters", 150.0))
    shape_type = req.border_shape or session.get("border_shape", "rectangle")
    
    cx, cy = None, None
    if center and len(center) == 2 and (center[0] != 0 or center[1] != 0):
        cx, cy = float(center[0]), float(center[1])
    else:
        for k in ("HIGHLIGHT", "CADASTRAL"):
            feats = session.get("layers", {}).get(k, {}).get("features", [])
            if feats:
                all_pts = []
                for f in feats:
                    c = f.get("coords", [])
                    if f.get("type") in ("Polygon", "MultiPolygon"):
                        from .exporter_dxf import _extract_rings
                        for ring in _extract_rings(c):
                            all_pts.extend(ring)
                    elif f.get("type") in ("LineString", "MultiLineString"):
                        from .exporter_dxf import _extract_lines
                        for line in _extract_lines(c):
                            all_pts.extend(line)
                    elif f.get("type") == "Point":
                        all_pts.append(c[0] if isinstance(c[0], (list, tuple)) else c)
                if all_pts:
                    cx = sum(p[0] for p in all_pts) / len(all_pts)
                    cy = sum(p[1] for p in all_pts) / len(all_pts)
                    break
                    
        if cx is None:
            bw = session.get("bounds_wgs84")
            if bw and len(bw) == 2:
                mid_lat = (bw[0][0] + bw[1][0]) / 2.0
                mid_lon = (bw[0][1] + bw[1][1]) / 2.0
                pts_src = transform_coords([(mid_lon, mid_lat)], "EPSG:4326", crs)
                cx, cy = pts_src[0]
                
    if cx is None or cy is None:
        raise HTTPException(status_code=400, detail="유효한 대상지 좌표를 찾을 수 없습니다. 주소를 다시 검색해 주세요.")
        
    border_poly = None
    if "BORDER" in session.get("layers", {}):
        border_poly = get_border_polygon(session["layers"])
        
    topo_layers = generate_topo_layers_for_parcel(
        cx=cx,
        cy=cy,
        buffer_meters=buf,
        crs=crs,
        border_shape=shape_type,
        border_poly=border_poly
    )
    
    session["layers"].update(topo_layers)
    session["center_coords"] = [cx, cy]
    session["buffer_meters"] = buf
    session["border_shape"] = shape_type
    
    if session.get("bounds_src") == [0, 0, 0, 0]:
        session["bounds_src"] = [cx - buf, cy - buf, cx + buf, cy + buf]
        
    all_summaries = []
    for l_key, l_data in session["layers"].items():
        all_summaries.append({
            "layer_name": str(l_key),
            "code": str(l_data.get("code", l_key)),
            "major": str(l_data.get("major", "기타")),
            "mid": str(l_data.get("mid", "기타")),
            "minor": str(l_data.get("minor", l_key)),
            "geom_type": str(l_data.get("geom_type", "Polygon")),
            "feature_count": int(len(l_data.get("features", []))),
            "style": l_data.get("style", {}),
            "has_elevation": bool(any(f.get("elevation") is not None and abs(f.get("elevation", 0)) > 1e-4 for f in l_data.get("features", [])))
        })
        
    return {
        "session_id": str(req.session_id),
        "address": str(session.get("address", "")),
        "topo_layer_keys": list(topo_layers.keys()),
        "layer_summaries": all_summaries,
        "center_coords": [cx, cy],
        "bounds_wgs84": session.get("bounds_wgs84"),
        "message": f"'{session.get('address', '검색 지번')}' 위치의 3D 수치지형도(등고선)가 결합되었습니다."
    }

@app.post("/api/preview")
def preview_layers(req: PreviewRequest):
    """Generate GeoJSON in WGS84 for the selected layers to preview in Leaflet."""
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다. 다시 업로드해주세요.")
        
    src_crs = session["crs"]
    all_layers = session["layers"]
    
    selected_data = {k: all_layers[k] for k in req.selected_layers if k in all_layers}
    if req.clip_to_border and "BORDER" in all_layers:
        border_poly = get_border_polygon(all_layers)
        if border_poly:
            selected_data = clip_layers_to_border(selected_data, border_poly)
    
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tf:
        geojson_path = tf.name
        
    try:
        export_geojson(selected_data, geojson_path, src_crs, target_crs="EPSG:4326")
        import json
        with open(geojson_path, "r", encoding="utf-8") as f:
            fc = json.load(f)
        return fc
    finally:
        if os.path.exists(geojson_path):
            os.remove(geojson_path)

@app.post("/api/export")
def export_custom_map(req: ExportRequest):
    """Export the customized map to DXF, GeoJSON, Shapefile (ZIP), or standalone HTML."""
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
    src_crs = session["crs"]
    all_layers = session["layers"]
    selected_data = {k: all_layers[k] for k in req.selected_layers if k in all_layers}
    
    if not selected_data:
        raise HTTPException(status_code=400, detail="선택된 레이어가 없습니다.")
        
    if req.clip_to_border and "BORDER" in all_layers:
        border_poly = get_border_polygon(all_layers)
        if border_poly:
            selected_data = clip_layers_to_border(selected_data, border_poly)
        
    addr_clean = re.sub(r'[^\w\-가-힣]', '_', session.get("address", "").strip()).strip('_')
    topo_clean = Path(session.get("file_name", "도면")).stem.replace(" ", "_").replace(",", "_")
    today_str = datetime.now().strftime("%Y%m%d")
    
    if addr_clean and addr_clean != "_":
        if topo_clean and topo_clean not in ("도면", addr_clean):
            base_name = f"[{addr_clean}]_({topo_clean})_현황도_{today_str}"
        else:
            base_name = f"[{addr_clean}]_현황도_{today_str}"
    else:
        base_name = f"{topo_clean}_현황도_{today_str}"

    temp_dir = Path(tempfile.mkdtemp(prefix="ngii_export_"))
    
    fmt = req.format.lower()
    target_crs = req.target_crs
    
    if fmt == "dxf":
        full_name = f"{base_name}.dxf"
        out_file = temp_dir / full_name
        meta = {
            "title": "수치지형도 & 지적도 통합 현황도",
            "address": session.get("address", "도면 대상지 일대"),
            "topo_name": topo_clean,
            "crs": target_crs if target_crs != "SAME" else src_crs,
            "buffer_meters": session.get("buffer_meters", 200),
            "border_shape": session.get("border_shape", "원형"),
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        export_dxf(
            selected_data,
            str(out_file),
            src_crs=src_crs,
            target_crs=target_crs,
            unify_bylayer=req.unify_bylayer,
            include_drawing_elements=req.include_drawing_elements,
            metadata=meta
        )
        enc_name = urllib.parse.quote(full_name)
        return FileResponse(
            str(out_file),
            filename=full_name,
            media_type="application/dxf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{enc_name}\"; filename*=UTF-8''{enc_name}",
                "X-Suggested-Filename": enc_name
            }
        )
    elif fmt == "geojson":
        full_name = f"{base_name}.geojson"
        out_file = temp_dir / full_name
        out_crs = target_crs if target_crs != "SAME" else src_crs
        export_geojson(selected_data, str(out_file), src_crs, out_crs)
        enc_name = urllib.parse.quote(full_name)
        return FileResponse(
            str(out_file),
            filename=full_name,
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f"attachment; filename=\"{enc_name}\"; filename*=UTF-8''{enc_name}",
                "X-Suggested-Filename": enc_name
            }
        )
    elif fmt == "shp":
        full_name = f"{base_name}_shp.zip"
        out_file = temp_dir / full_name
        export_shp_zip(selected_data, str(out_file), src_crs, target_crs)
        enc_name = urllib.parse.quote(full_name)
        return FileResponse(
            str(out_file),
            filename=full_name,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=\"{enc_name}\"; filename*=UTF-8''{enc_name}",
                "X-Suggested-Filename": enc_name
            }
        )
    elif fmt == "html":
        full_name = f"{base_name}_viewer.html"
        out_file = temp_dir / full_name
        geojson_temp = temp_dir / "temp.geojson"
        export_geojson(selected_data, str(geojson_temp), src_crs, target_crs="EPSG:4326")
        import json
        with open(geojson_temp, "r", encoding="utf-8") as gf:
            geojson_data = gf.read()
            
        html_template = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>{base_name} - 통합 수치지형·지적도 뷰어</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body, html {{ margin: 0; padding: 0; height: 100%; font-family: sans-serif; }}
    #map {{ height: 100vh; width: 100%; }}
    .info-box {{
      position: absolute; top: 10px; right: 10px; z-index: 1000;
      background: rgba(255,255,255,0.95); padding: 12px 18px;
      border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      max-width: 320px; font-size: 13px;
    }}
    .info-box h3 {{ margin: 0 0 6px 0; font-size: 15px; color: #1e293b; }}
  </style>
</head>
<body>
  <div class="info-box">
    <h3>{base_name}</h3>
    <p>수치지형도 & VWorld 지적도 통합 추출<br>레이어 수: {len(selected_data)}개</p>
  </div>
  <div id="map"></div>
  <script>
    var map = L.map('map').setView([37.5665, 126.9780], 13);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    var data = {geojson_data};
    var layer = L.geoJSON(data, {{
      style: function(feat) {{
        var p = feat.properties || {{}};
        return {{
          color: p.color || '#3388ff',
          weight: p.layer === 'HIGHLIGHT' ? 3 : 1.5,
          opacity: 0.9,
          fillOpacity: p.layer === 'HIGHLIGHT' ? 0.45 : 0.25
        }};
      }},
      onEachFeature: function(feat, l) {{
        var p = feat.properties;
        var popup = '<b>' + (p.minor || p.layer) + '</b><br>' +
                    '코드: ' + (p.code || '-') + '<br>' +
                    (p.JIBUN ? '지번: ' + p.JIBUN + '<br>' : '') +
                    (p.elevation ? '표고: ' + p.elevation + 'm<br>' : '');
        l.bindPopup(popup);
      }}
    }}).addTo(map);

    if (layer.getBounds().isValid()) {{
      map.fitBounds(layer.getBounds(), {{ padding: [30, 30] }});
    }}
  </script>
</body>
</html>"""
        out_file.write_text(html_template, encoding="utf-8")
        return FileResponse(
            str(out_file),
            filename=f"{base_name}_viewer.html",
            media_type="text/html"
        )
    else:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 포맷: {fmt}")

# Mount static web UI (support both /static/... and root /...)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static_files")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
