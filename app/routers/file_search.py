from fastapi import APIRouter

from app.core.kernel32_search import DiskIndexer

router = APIRouter()

indexer = DiskIndexer()
indexer.build_index()


@router.get("/v1/search")
def search(query: str, search_type: str = None):
    """
    文件搜索接口
    - q: 关键字
    返回: [{"name": 文件名, "size": 文件大小, "path": 文件完整路径}, ...]
    """
    results = indexer.search(query, search_type)
    return results
