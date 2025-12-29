from fastapi import APIRouter

from app.core.kernel32_search import DiskIndexer
from app.vo.file_search import SearchRequest

router = APIRouter()

indexer = DiskIndexer()

@router.get("/v1/search")
def search(query: str, file_type: str = None):
    """
    文件搜索接口
    - q: 关键字
    返回: [{"name": 文件名, "size": 文件大小, "path": 文件完整路径}, ...]
    """
    searchQuery = SearchRequest()
    searchQuery.keyword = query
    searchQuery.file_type = file_type
    results = indexer.search(searchQuery)
    return results


@router.get("/v1/reload/index")
def reload_index():
    """
    文件搜索接口
    - q: 关键字
    返回: [{"name": 文件名, "size": 文件大小, "path": 文件完整路径}, ...]
    """
    indexer.update_index()
