import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ..db import connect
from ..embeddings import EmbeddingUnavailable
from ..schemas import ChatRequest, ChatTurn, SourceOut

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger("docmind.chat")


def sse(event: str, data: object) -> str:
    """One Server-Sent Events message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def retrieval_query(question: str, history: list[ChatTurn]) -> str:
    """
    Follow-ups like "and the deadline?" retrieve poorly on their own, so short questions borrow
    the previous user question for context. (A model-written standalone question would be better
    but costs an extra round trip.)
    """
    previous = next((t.content for t in reversed(history) if t.role == "user"), None)
    if previous and len(question.split()) <= 6:
        return f"{previous} {question}"
    return question


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "The AI provider rejected the API key. Check LLM_API_KEY on the server."
    if name == "RateLimitError":
        return "The AI provider's rate limit was hit. Wait a moment and ask again."
    if name in {"APIConnectionError", "APITimeoutError"}:
        return "Couldn't reach the AI provider. Check LLM_BASE_URL and the server's internet connection."
    if name == "NotFoundError":
        return "The AI provider doesn't recognise the model name. Check LLM_MODEL."
    return "The answer stopped because of an error on the server. Try asking again."


@router.post("/chat")
def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """
    Streams an answer as Server-Sent Events:
    `sources` (the numbered passages) first, then `token` events as text arrives, then `done`.
    """
    state = request.app.state
    with connect(state.settings.db_path) as conn:
        rows = conn.execute("select id from documents where status = 'ready'").fetchall()
    ready = [r["id"] for r in rows]
    scope = [d for d in body.document_ids if d in ready] if body.document_ids else ready
    if not scope:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "None of the selected documents are ready yet."
            if body.document_ids
            else "Upload a document first.",
        )

    try:
        passages = state.retriever.search(
            retrieval_query(body.question, body.history), scope, state.settings.top_k
        )
    except EmbeddingUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    history = [t.model_dump() for t in body.history]

    def events() -> Iterator[str]:
        sources = [
            SourceOut(number=i, **{k: v for k, v in vars(p).items()}).model_dump()
            for i, p in enumerate(passages, start=1)
        ]
        yield sse("sources", sources)
        try:
            for token in state.generator.stream(body.question, passages, history):
                yield sse("token", {"text": token})
        except Exception as exc:
            log.exception("Answer generation failed")
            yield sse("error", {"message": friendly_error(exc)})
        yield sse("done", {})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },  # don't let proxies buffer the stream
    )
