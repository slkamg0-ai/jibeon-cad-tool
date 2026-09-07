import os
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import requests
from dotenv import load_dotenv

# Try loading .env from current dir or project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
CADASTRAL_LAYER = "LP_PA_CBND_BUBUN"

DEFAULT_API_KEY = "B2C87AF7-CF6E-310D-8405-EDDC5A5D6B91"

class VWorldClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("VWORLD_API_KEY") or DEFAULT_API_KEY

    def search_parcel(self, address: str) -> Dict[str, Any]:
        """Search address to find target parcel PNU and center coordinates (EPSG:5186)."""
        params = {
            "service": "search",
            "request": "search",
            "query": address.strip(),
            "type": "address",
            "category": "parcel",
            "format": "json",
            "crs": "EPSG:5186",
            "key": self.api_key,
        }
        res = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        items = data.get("response", {}).get("result", {}).get("items", [])
        if not items:
            # Try type="both" or type="place"
            params["type"] = "both"
            res2 = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
            if res2.ok:
                items = res2.json().get("response", {}).get("result", {}).get("items", [])
                
        if not items:
            raise ValueError(f"'{address}'에 해당하는 지번/주소를 찾을 수 없습니다. 정확한 지번을 입력해 주세요.")
            
        item = items[0]
        point = item["point"]
        addr_info = item.get("address", {})
        display_addr = addr_info.get("parcel") or addr_info.get("road") or address
        
        return {
            "pnu": item.get("id", ""),
            "address": display_addr,
            "x": float(point["x"]),
            "y": float(point["y"]),
            "crs": "EPSG:5186"
        }

    def download_cadastral(
        self,
        center_x: float,
        center_y: float,
        target_pnu: str,
        buffer_meters: float = 100.0,
        crs: str = "EPSG:5186"
    ) -> List[Dict[str, Any]]:
        """Fetch surrounding cadastral parcel boundaries via VWorld WFS with multi-page support."""
        min_x = center_x - buffer_meters
        min_y = center_y - buffer_meters
        max_x = center_x + buffer_meters
        max_y = center_y + buffer_meters
        
        all_features = []
        page = 1
        max_pages = 6  # Up to 6,000 features, supporting up to 1000m+ buffers
        
        while page <= max_pages:
            params = {
                "service": "data",
                "request": "GetFeature",
                "data": CADASTRAL_LAYER,
                "key": self.api_key,
                "geomFilter": f"BOX({min_x},{min_y},{max_x},{max_y})",
                "geometry": "true",
                "attribute": "true",
                "crs": crs,
                "format": "json",
                "size": "1000",
                "page": str(page)
            }
            try:
                res = requests.get(VWORLD_DATA_URL, params=params, timeout=15)
                res.raise_for_status()
                data = res.json()
            except Exception as e:
                if page > 1 and all_features:
                    break
                raise ValueError(f"VWorld 지적도 API 호출 실패: {e}")
                
            response = data.get("response", {})
            status = response.get("status")
            if status != "OK":
                if page == 1:
                    # If status is NOT_FOUND or similar, return empty instead of crashing
                    return []
                break
                
            features = response.get("result", {}).get("featureCollection", {}).get("features", [])
            if not features:
                break
                
            all_features.extend(features)
            
            page_info = response.get("page", {})
            total_pages = int(page_info.get("total", 1))
            if page >= total_pages:
                break
            page += 1
            
        return all_features

