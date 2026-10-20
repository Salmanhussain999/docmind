import numpy as np

from app.embeddings import HashEmbedder
from app.retrieval import fts_query, reciprocal_rank_fusion
from tests.conftest import upload, wait_ready


def test_rrf_rewards_agreement_between_rankings():
    scores = reciprocal_rank_fusion([1, 2, 3], [3, 1, 4])
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    # Chunks that appear in both lists outrank chunks that only one method found.
    assert ranked == [1, 3, 2, 4]


def test_fts_query_is_safe_for_any_input():
    assert fts_query('what\'s "AND" OR (NEAR) -- ?') == '"what" OR "and" OR "or" OR "near"'
    assert fts_query("?!") is None


def test_hash_embedder_is_normalised_and_deterministic():
    e = HashEmbedder()
    a = e.embed_query("annual leave policy")
    assert np.isclose(np.linalg.norm(a), 1.0)
    assert np.array_equal(a, e.embed_query("annual leave policy"))
    related = float(a @ e.embed_query("leave policy for annual holidays"))
    unrelated = float(a @ e.embed_query("submit receipts to finance"))
    assert related > unrelated


def test_hybrid_search_finds_the_right_page(client):
    doc = wait_ready(client, upload(client)["id"])
    retriever = client.app.state.retriever

    passages = retriever.search("How many days of paid annual leave?", [doc["id"]], top_k=3)
    assert passages[0].page == 2
    assert "twenty days" in passages[0].text

    passages = retriever.search("travel approval department head", [doc["id"]], top_k=3)
    assert passages[0].page == 3


def test_search_is_scoped_to_the_given_documents(client):
    first = wait_ready(client, upload(client, "a.pdf")["id"])
    second = wait_ready(client, upload(client, "b.pdf")["id"])
    retriever = client.app.state.retriever

    passages = retriever.search("remote work", [second["id"]], top_k=5)
    assert passages and all(p.document_id == second["id"] for p in passages)
    assert first["id"] != second["id"]
