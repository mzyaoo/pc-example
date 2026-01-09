from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
from pydantic import BaseModel

router = APIRouter()


class StreamReq(BaseModel):
    user_id: int
    task_id: str
    mode: str


async def event_stream(request: Request, params: StreamReq):
    try:
        for i in range(100):
            if await request.is_disconnected():
                print("客户端断开，参数是：", params.dict())
                break

            yield f"data: {i}\n\n"
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("流被取消，参数是：", params.dict())
        raise


@router.post("/stream")
async def stream(
        request: Request,
        body: StreamReq,
):
    return StreamingResponse(
        event_stream(request, body),
        media_type="text/event-stream"
    )


@router.get("/")
def health_check():
    return {"status": "ok"}
