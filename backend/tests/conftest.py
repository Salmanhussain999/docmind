import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.embeddings import HashEmbedder
from app.llm import ExtractiveGenerator
from tests.pdf_factory import make_pdf

HANDBOOK = [
    [
        "Northwind Employee Handbook",
        "Remote work policy. Employees may work remotely up to three days per week.",
        "Remote days must be agreed with your manager one week in advance.",
    ],
    [
        "Leave policy. Full-time employees receive twenty days of paid annual leave.",
        "Unused leave can be carried over, up to a maximum of five days.",
        "Sick leave does not count towards annual leave.",
    ],
    [
        "Expenses. Submit receipts in the finance portal within thirty days.",
        "Travel above 500 dollars needs approval from the department head before booking.",
    ],
]


class ScriptedGenerator:
    """Streams a fixed answer and records what it was given, so tests can check the prompt inputs."""

    mode = "llm"
    model = "scripted"

    def __init__(self, tokens: list[str] | None = None, fail: Exception | None = None):
        self.tokens = tokens or ["Employees get ", "twenty days ", "of leave [1]."]
        self.fail = fail
        self.calls: list[dict] = []

    def stream(self, question, passages, history):
        self.calls.append({"question": question, "passages": passages, "history": history})
        yield from self.tokens[:1]
        if self.fail:
            raise self.fail
        yield from self.tokens[1:]


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        embedding_provider="hash",
        llm_provider="extractive",
        chunk_size=300,
        chunk_overlap=60,
        top_k=4,
        max_upload_mb=1,
        max_pages=10,
    )


def make_client(settings: Settings, generator=None) -> TestClient:
    from app.main import create_app

    return TestClient(
        create_app(settings, embedder=HashEmbedder(), generator=generator or ExtractiveGenerator())
    )


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    with make_client(settings) as c:
        yield c


def upload(client: TestClient, name: str = "handbook.pdf", data: bytes | None = None) -> dict:
    data = make_pdf(HANDBOOK) if data is None else data
    res = client.post("/api/documents", files={"file": (name, data, "application/pdf")})
    assert res.status_code == 202, res.text
    return res.json()


def wait_ready(client: TestClient, document_id: str, timeout: float = 10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        doc = client.get(f"/api/documents/{document_id}").json()
        if doc["status"] != "processing":
            return doc
        time.sleep(0.05)
    raise AssertionError("document never finished processing")


def parse_sse(body: str) -> list[tuple[str, object]]:
    import json

    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        events.append((lines["event"], json.loads(lines["data"])))
    return events
