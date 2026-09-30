"""CDN 라우트 - 에셋번들 로컬 서빙.

원격: https://oss01.aliother.com/v310/202608022111/
로컬: http://127.0.0.1:8888/cdn/v310/202608022111/
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# update_data/com.Alioth.JusticeSchool.cn/files/AssetBundles/Android/
# -> CDN의 /v310/202608022111/AssetBundles/Android/ 에 대응
BASE_DIR = Path(__file__).parent.parent / "update_data" / "com.Alioth.JusticeSchool.cn" / "files"


@router.get("/cdn/v310/202608022111/{file_path:path}")
async def serve_cdn(file_path: str):
    """CDN 파일 서빙."""
    # 경로 탐색 방지
    full_path = (BASE_DIR / file_path).resolve()
    if not str(full_path).startswith(str(BASE_DIR.resolve())):
        raise HTTPException(status_code=403, detail="forbidden")

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="not found")

    return FileResponse(
        path=str(full_path),
        media_type="application/octet-stream",
    )


@router.get("/cdn/v310/202608022111/AssetBundleInfoFile.json")
async def serve_bundle_info():
    """번들 정보 JSON."""
    path = BASE_DIR / "AssetBundles" / "Android" / "AssetBundleInfoFile.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path=str(path), media_type="application/json")
