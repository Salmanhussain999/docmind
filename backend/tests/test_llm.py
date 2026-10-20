import json

import httpx
from openai import OpenAI

from app.config import Settings
from app.llm import ExtractiveGenerator, OpenAICompatibleGenerator, build_messages, create_generator
from app.retrieval import Passage

PASSAGES = [
    Passage(
        1, "doc", "handbook.pdf", 2, "Full-time employees receive twenty days of paid annual leave.", 0.03
    ),
    Passage(2, "doc", "handbook.pdf", 2, "Unused leave can be carried over, up to five days.", 0.02),
]


def openai_stream(*pieces: str) -> bytes:
    """What an OpenAI-compatible server sends for a streamed chat completion."""
    events = []
    for piece in pieces:
        chunk = {
            "id": "c1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "test-model",
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        events.append(f"data: {json.dumps(chunk)}\n\n")
    events.append("data: [DONE]\n\n")
    return "".join(events).encode()


def test_streams_tokens_from_an_openai_compatible_server():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=openai_stream("Twenty ", "days [1]."),
            headers={"content-type": "text/event-stream"},
        )

    settings = Settings(llm_api_key="test-key", llm_model="test-model", embedding_provider="hash")
    generator = OpenAICompatibleGenerator(settings)
    generator.client = OpenAI(
        api_key="test-key",
        base_url="https://llm.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    tokens = list(generator.stream("How much leave?", PASSAGES, []))

    assert tokens == ["Twenty ", "days [1]."]
    sent = requests[0]
    assert sent["model"] == "test-model"
    assert sent["stream"] is True
    assert "temperature" not in sent  # only sent when configured
    assert "[1] (handbook.pdf, page 2)" in sent["messages"][-1]["content"]


def test_prompt_keeps_recent_history_and_numbers_excerpts():
    history = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    messages = build_messages("Now?", PASSAGES, history)

    assert messages[0]["role"] == "system"
    assert [m["content"] for m in messages[1:-1]] == [f"q{i}" for i in range(4, 10)]
    last = messages[-1]["content"]
    assert last.index("[1]") < last.index("[2]") < last.index("Question: Now?")


def test_generator_choice_follows_configuration():
    assert isinstance(create_generator(Settings(embedding_provider="hash")), ExtractiveGenerator)
    keyless_local = Settings(llm_base_url="http://localhost:11434/v1", embedding_provider="hash")
    assert isinstance(create_generator(keyless_local), OpenAICompatibleGenerator)


def test_extractive_answers_quote_and_cite():
    answer = "".join(ExtractiveGenerator().stream("How many days of annual leave?", PASSAGES, []))
    assert "twenty days of paid annual leave" in answer
    assert "[1]" in answer

    nothing = "".join(ExtractiveGenerator().stream("anything", [], []))
    assert "couldn't find" in nothing
