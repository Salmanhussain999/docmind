from typing import Literal

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    name: str
    media_type: str
    size_bytes: int
    page_count: int
    chunk_count: int
    status: Literal["processing", "ready", "failed"]
    error: str | None
    created_at: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Empty means "search every ready document".
    document_ids: list[str] = Field(default_factory=list, max_length=50)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class SourceOut(BaseModel):
    number: int
    chunk_id: int
    document_id: str
    document_name: str
    page: int
    text: str
    score: float


class HealthOut(BaseModel):
    status: Literal["ok"]
    answer_mode: Literal["llm", "extractive"]
    model: str
    embeddings: str
