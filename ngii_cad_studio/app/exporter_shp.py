import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
import shapefile
from .crs_converter import transform_coords

def export_shp_zip(
    selected_layers: Dict[str, Dict[str, Any]],
    output_zip_path: str,
    src_crs: str,
    target_crs: str = "SAME"
) -> str:
    """Generate ESRI Shapefile package (.zip) for selected layers."""
    temp_dir = Path(tempfile.mkdtemp(prefix="shp_export_"))
    try:
        need_transform = (target_crs != "SAME" and target_crs != src_crs)
        out_crs = target_crs if target_crs != "SAME" else src_crs
        
        for layer_id, l_data in selected_layers.items():
            code = l_data.get("code", layer_id)
            clean_name = f"{code}".replace(" ", "_")
            shp_path = temp_dir / clean_name
            
            features = l_data.get("features", [])
            if not features:
                continue
                
            # Determine geometry type for shapefile writer
            types = [f.get("type", "LineString") for f in features]
            geom_type = max(set(types), key=types.count)
            
            if geom_type == "Point":
                w = shapefile.Writer(str(shp_path), shapeType=shapefile.POINT, encoding="cp949")
            elif geom_type == "Polygon":
                w = shapefile.Writer(str(shp_path), shapeType=shapefile.POLYGON, encoding="cp949")
            else:
                w = shapefile.Writer(str(shp_path), shapeType=shapefile.POLYLINE, encoding="cp949")
                
            w.field("CODE", "C", size=20)
            w.field("NAME", "C", size=50)
            w.field("ELEV", "N", decimal=2)
            
            for feat in features:
                coords = feat.get("coords", [])
                elev = feat.get("elevation", 0.0) or 0.0
                if not coords:
                    continue
                    
                if need_transform:
                    if geom_type == "Point":
                        coords = transform_coords(coords, src_crs, out_crs)
                    else:
                        coords = transform_coords(coords, src_crs, out_crs)
                        
                if geom_type == "Point":
                    w.point(coords[0][0], coords[0][1])
                elif geom_type == "Polygon":
                    w.poly([coords])
                else:
                    w.line([coords])
                    
                w.record(
                    CODE=str(code),
                    NAME=str(l_data.get("minor", ""))[:45],
                    ELEV=float(elev)
                )
                
            w.close()
            
        # Create zip
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in temp_dir.glob("*"):
                zf.write(file, arcname=file.name)
                
        return output_zip_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
