# tests/test_tools.py
import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from agent import run_agent

from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# search_listings()
def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 20 for item in results)
    
def test_search_size_filter():
    """Size filter is case-insensitive substring (spec: 'M' matches 'S/M')."""
    results = search_listings("tee", size="m", max_price=None)  # lowercase on purpose
    assert all("m" in item["size"].lower() for item in results)

def test_search_sorted_by_relevance():
    """Best keyword match comes first (scores are non-increasing)."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    kws = "vintage graphic tee".split()
    def score(item):
        hay = " ".join([item["title"], item["description"], *item["style_tags"]]).lower()
        return sum(k in hay for k in kws)
    scores = [score(item) for item in results]
    assert scores == sorted(scores, reverse=True)   # already ordered best-first

def test_search_results_have_expected_keys():
    """Each result is a full listing dict (the shape you promised callers)."""
    results = search_listings("denim jacket", max_price=None)
    assert results, "expected at least one match"
    expected = {"id", "title", "description", "category", "style_tags",
                "size", "condition", "price", "colors", "brand", "platform"}
    assert expected <= results[0].keys()

# suggest_outfit()
# suggest_outfit calls the live Groq LLM — skip these when no key is configured.
needs_api = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — skipping live LLM test",
)

# Garment keywords drawn from the example wardrobe (data/wardrobe_schema.json).
WARDROBE_WORDS = [
    "jeans", "trousers", "tank", "crewneck", "sweatshirt", "hoodie",
    "jacket", "sneakers", "boots", "belt", "bag",
]

@needs_api
def test_suggest_outfit_names_wardrobe_piece():
    """1. Real item + example wardrobe → non-empty string naming a wardrobe piece."""
    item = search_listings("vintage graphic tee", max_price=30)[0]
    out = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(out, str) and out.strip()                 # non-empty
    assert any(word in out.lower() for word in WARDROBE_WORDS)  # references the closet


@needs_api
def test_suggest_outfit_empty_wardrobe_general_advice():
    """2. Real item + empty wardrobe → non-empty general advice, no crash."""
    item = search_listings("vintage graphic tee", max_price=30)[0]
    out = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(out, str) and out.strip()   # graceful, non-empty
    # NOTE: we intentionally do NOT assert "zero garment words appear." General
    # styling advice naturally mentions categories like "jeans"/"sneakers", so a
    # strict "no wardrobe pieces named" check would flake with a live LLM. The
    # real contract for the empty-wardrobe branch is: non-empty, no exception.


@needs_api
def test_suggest_outfit_stable_across_calls():
    """3. Same input twice → both succeed without crashing (text may differ)."""
    item = search_listings("vintage graphic tee", max_price=30)[0]
    first = suggest_outfit(item, get_example_wardrobe())
    second = suggest_outfit(item, get_example_wardrobe())
    assert first.strip() and second.strip()   # both non-empty; difference is fine

# test failure cases

def test_suggest_outfit_survives_llm_failure(monkeypatch):
    """API failure → returns a non-empty fallback string, never raises."""
    def boom():
        raise RuntimeError("API down")
    monkeypatch.setattr("tools._get_groq_client", boom)

    item = search_listings("vintage graphic tee", max_price=30)[0]
    out = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(out, str) and out.strip()   # caught, fell back, no crash

def test_suggest_outfit_handles_empty_llm_response(monkeypatch):
    """LLM returns empty content → fallback string, not ''."""
    class _Msg:        content = ""
    class _Choice:     message = _Msg()
    class _Resp:       choices = [_Choice()]
    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):  return _Resp()
    monkeypatch.setattr("tools._get_groq_client", lambda: _Client())

    item = search_listings("vintage graphic tee", max_price=30)[0]
    out = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(out, str) and out.strip()   # never returns empty

@needs_api
def test_suggest_outfit_wardrobe_missing_items_key():
    item = search_listings("vintage graphic tee", max_price=30)[0]
    out = suggest_outfit(item, {})   # no "items" key at all
    assert isinstance(out, str) and out.strip()


# suggest_outfit()

# create_fit_card()

@needs_api
def test_create_fit_card_mentions_price_and_platform():
    """1. Real outfit + real item → caption that mentions the price and platform."""
    item = search_listings("vintage graphic tee", max_price=30)[0]
    outfit = "Pair it with baggy jeans and chunky sneakers for an easy 90s look."
    card = create_fit_card(outfit, item)
    assert isinstance(card, str) and card.strip()         # non-empty caption
    assert item["platform"].lower() in card.lower()       # platform mentioned
    assert str(int(item["price"])) in card                # price mentioned (e.g. "18")


def test_create_fit_card_empty_outfit_returns_error():
    """2. outfit='' → descriptive error string, not a crash, not empty (no LLM call)."""
    item = search_listings("vintage graphic tee", max_price=30)[0]
    msg = create_fit_card("", item)
    assert isinstance(msg, str) and msg.strip()           # informative error string
    # whitespace-only outfit hits the same guard
    assert create_fit_card("   ", item).strip()


@needs_api
def test_create_fit_card_varies_across_items():
    """3. Two different items → captions differ (proves temperature/variety)."""
    items = search_listings("vintage", max_price=80)
    item_a, item_b = items[0], items[1]
    outfit = "Style it with your favorite jeans and boots."
    card_a = create_fit_card(outfit, item_a)
    card_b = create_fit_card(outfit, item_b)
    assert card_a.strip() and card_b.strip()
    assert card_a != card_b                               # different inputs → different captions

# run_agent() — the planning loop

@needs_api
def test_run_agent_happy_path():
    """Match → full pipeline runs; all output fields populated, no error."""
    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    assert session["error"] is None
    assert session["parsed"]["description"]            # query was parsed
    assert len(session["search_results"]) > 0          # search found matches
    assert session["selected_item"] is not None        # top result selected
    assert isinstance(session["fit_card"], str) and session["fit_card"].strip()


def test_run_agent_no_results_stops_before_llm():
    """No match → Step 3 early-return. suggest_outfit/create_fit_card NOT called.

    Deterministic (no LLM, no API key). This is the core branching proof: the
    LLM output fields stay None because the loop never reached those tools.
    """
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    assert session["error"] is not None                # helpful message set
    assert session["search_results"] == []             # search returned nothing
    assert session["selected_item"] is None            # never selected
    assert session["outfit_suggestion"] is None        # suggest_outfit skipped
    assert session["fit_card"] is None                 # create_fit_card skipped


def test_run_agent_unparseable_stops_before_search():
    """No describable item → Step 2 early-return; search never runs."""
    session = run_agent("under $20", get_example_wardrobe())
    assert session["error"] is not None
    assert session["search_results"] == []             # never searched
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_run_agent_branches_give_distinct_errors():
    """Two different bad inputs → two different error messages (proves conditional logic,
    not one fixed sequence)."""
    no_results = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    unparseable = run_agent("under $20", get_example_wardrobe())
    assert no_results["error"] != unparseable["error"]

# Trigger create_fit_card with an empty outfit string:
# python -c "
# from tools import search_listings, create_fit_card
# results = search_listings('vintage graphic tee', size=None, max_price=50)
# print(create_fit_card('', results[0]))"
# Confirm it returns a descriptive error message string — not a Python exception.


