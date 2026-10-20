from app.config import Settings
from tests.conftest import ScriptedGenerator, make_client, parse_sse, upload, wait_ready
from tests.pdf_factory import make_pdf


def test_health_reports_answer_mode(client):
    assert client.get("/api/health").json() == {
        "status": "ok",
        "answer_mode": "extractive",
        "model": "extractive",
        "embeddings": "hash",
    }


def test_upload_processes_in_the_background(client):
    doc = upload(client)
    assert doc["status"] == "processing"
    assert doc["name"] == "handbook.pdf"

    ready = wait_ready(client, doc["id"])
    assert ready["status"] == "ready"
    assert ready["page_count"] == 3
    assert ready["chunk_count"] >= 3
    assert [d["id"] for d in client.get("/api/documents").json()] == [doc["id"]]


def test_upload_accepts_text_and_markdown(client):
    res = client.post(
        "/api/documents",
        files={"file": ("notes.md", b"# Notes\n\nThe launch is on Friday.", "text/markdown")},
    )
    assert res.status_code == 202
    assert wait_ready(client, res.json()["id"])["status"] == "ready"


def test_upload_rejects_bad_files(client):
    def post(name, data):
        return client.post("/api/documents", files={"file": (name, data, "application/octet-stream")})

    assert post("photo.png", b"\x89PNG").status_code == 415
    assert post("fake.pdf", b"hello").status_code == 400
    assert post("empty.txt", b"").status_code == 400
    too_big = post("big.txt", b"x" * (1024 * 1024 + 1))
    assert too_big.status_code == 413
    assert "1 MB" in too_big.json()["detail"]


def test_unreadable_pdf_is_marked_failed_with_a_reason(client):
    doc = upload(client, "scan.pdf", make_pdf([[], []]))
    failed = wait_ready(client, doc["id"])
    assert failed["status"] == "failed"
    assert "scanned" in failed["error"]


def test_original_file_can_be_opened_inline(client):
    data = make_pdf([["Hello."]])
    doc = wait_ready(client, upload(client, "hello.pdf", data)["id"])
    res = client.get(f"/api/documents/{doc['id']}/file")
    assert res.status_code == 200
    assert res.content == data
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith("inline")


def test_delete_removes_document_chunks_and_search_results(client):
    doc = wait_ready(client, upload(client)["id"])
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/documents/{doc['id']}").status_code == 404
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 404

    from app.db import connect

    with connect(client.app.state.settings.db_path) as conn:
        assert conn.execute("select count(*) from chunks").fetchone()[0] == 0
        # The full-text index is cleaned up by the delete trigger, via the cascade.
        assert (
            conn.execute("select count(*) from chunks_fts where chunks_fts match 'leave'").fetchone()[0] == 0
        )


def test_chat_needs_a_ready_document(client):
    res = client.post("/api/chat", json={"question": "Anything?"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Upload a document first."


def test_chat_streams_sources_then_tokens(client):
    wait_ready(client, upload(client)["id"])
    with client.stream(
        "POST", "/api/chat", json={"question": "How many days of annual leave do I get?"}
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(res.read().decode())

    kinds = [kind for kind, _ in events]
    assert kinds[0] == "sources" and kinds[-1] == "done"
    assert "token" in kinds

    sources = events[0][1]
    assert sources[0]["number"] == 1
    assert {"document_name", "page", "text", "chunk_id"} <= set(sources[0])

    answer = "".join(data["text"] for kind, data in events if kind == "token")
    assert "twenty days" in answer
    assert "[1]" in answer or "[2]" in answer


def test_chat_passes_history_and_condenses_follow_ups(settings: Settings):
    generator = ScriptedGenerator()
    with make_client(settings, generator) as client:
        wait_ready(client, upload(client)["id"])
        history = [
            {"role": "user", "content": "What is the remote work policy?"},
            {"role": "assistant", "content": "Up to three days a week [1]."},
        ]
        with client.stream(
            "POST", "/api/chat", json={"question": "Who approves it?", "history": history}
        ) as res:
            parse_sse(res.read().decode())

    call = generator.calls[0]
    assert call["question"] == "Who approves it?"
    assert call["history"] == history
    # The short follow-up retrieved with the previous question's context.
    assert any("manager" in p.text for p in call["passages"])


def test_chat_reports_model_errors_in_the_stream(settings: Settings):
    class AuthenticationError(Exception):
        pass

    with make_client(settings, ScriptedGenerator(fail=AuthenticationError("bad key"))) as client:
        wait_ready(client, upload(client)["id"])
        with client.stream("POST", "/api/chat", json={"question": "Leave?"}) as res:
            events = parse_sse(res.read().decode())

    kinds = [k for k, _ in events]
    assert kinds == ["sources", "token", "error", "done"]
    assert "API key" in events[2][1]["message"]


def test_chat_can_be_limited_to_selected_documents(client):
    first = wait_ready(client, upload(client, "first.pdf")["id"])
    wait_ready(client, upload(client, "second.pdf")["id"])

    with client.stream("POST", "/api/chat", json={"question": "leave", "document_ids": [first["id"]]}) as res:
        sources = parse_sse(res.read().decode())[0][1]
    assert sources and all(s["document_id"] == first["id"] for s in sources)

    res = client.post("/api/chat", json={"question": "leave", "document_ids": ["missing"]})
    assert res.status_code == 400


def test_embedding_outage_fails_the_upload_with_a_clear_message(settings: Settings):
    from fastapi.testclient import TestClient

    from app.embeddings import EmbeddingUnavailable
    from app.llm import ExtractiveGenerator
    from app.main import create_app

    class OfflineEmbedder:
        name = "local"

        def embed_passages(self, texts):
            raise EmbeddingUnavailable("Couldn't download the embedding model.")

        def embed_query(self, text):
            raise EmbeddingUnavailable("Couldn't download the embedding model.")

    app = create_app(settings, embedder=OfflineEmbedder(), generator=ExtractiveGenerator())
    with TestClient(app) as client:
        doc = wait_ready(client, upload(client)["id"])
        assert doc["status"] == "failed"
        assert "embedding model" in doc["error"]
