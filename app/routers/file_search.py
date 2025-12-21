from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/search/{query}")
def search(query: str, search_type: str):
    # results, count, duration = searcher.search(search_query, file_type=filter_type)
    #
    # print(f"\n--- 找到 {count} 个结果 (耗时: {duration:.4f}s) ---")
    # if count > 0:
    #     print(results)
    # else:
    #     print("未找到匹配项。")
    return {}
