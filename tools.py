"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # Replace this with your implementation
    listings = load_listings()

    # Keywords from the description, lowercased and split on whitespace.
    keywords = description.lower().split()

    results = []
    for listing in listings:
        # Filter by price ceiling (inclusive).
        if max_price is not None and listing["price"] > max_price:
            continue

        # Filter by size (case-insensitive substring, e.g. "M" matches "S/M").
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        # Score by keyword overlap with title + description + style_tags.
        haystack = " ".join(
            [listing["title"], listing["description"], *listing["style_tags"]]
        ).lower()
        score = sum(1 for kw in keywords if kw in haystack)

        # Drop listings with no relevant matches.
        if score == 0:
            continue

        results.append((score, listing))

    # Sort by score (highest first); break ties by lower price.
    results.sort(key=lambda pair: (-pair[0], pair[1]["price"]))

    return [listing for _, listing in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
        # Describe the new item for the prompt.
    item_desc = (
        f"{new_item['title']} — {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])}. "
        f"{new_item['description']}"
    )

    items = wardrobe.get("items", [])

    if not items:
        # Empty wardrobe: ask for general styling advice for the item alone.
        prompt = (
            "You are a thrift styling assistant. The user is considering buying "
            "this second-hand item but has not entered any wardrobe yet:\n\n"
            f"{item_desc}\n\n"
            "Suggest 1-2 complete outfit ideas built around this piece. Since you "
            "don't know their closet, describe the kinds of pieces (categories, "
            "colors, vibe) that pair well with it and what aesthetic it suits. "
            "Keep it to a short, friendly paragraph."
        )
    else:
        # Non-empty wardrobe: format the closet and ask for specific combinations.
        wardrobe_lines = "\n".join(
            f"- {it['name']} ({it['category']}; "
            f"{', '.join(it['colors'])}; {', '.join(it['style_tags'])})"
            for it in items
        )
        prompt = (
            "You are a thrift styling assistant. The user is considering buying "
            "this second-hand item:\n\n"
            f"{item_desc}\n\n"
            "Here is the user's existing wardrobe:\n"
            f"{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that combine the new item with specific "
            "pieces NAMED from their wardrobe above. Reference the wardrobe pieces "
            "by name. Keep it to a short, friendly paragraph."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        suggestion = (response.choices[0].message.content or "").strip()
    except Exception as e:
        suggestion = ""

    # Never return an empty string — fall back to a graceful message.
    if not suggestion:
        return (
            f"Couldn't generate outfit ideas for the {new_item['title']} right now — "
            "try again in a moment."
        )

    return suggestion


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
# Guard: empty or whitespace-only outfit → descriptive error, never raise.
    if not outfit or not outfit.strip():
        return (
            "Can't write a fit card without an outfit suggestion — "
            "run suggest_outfit() first."
        )

    # Give the LLM the item details (name, price, platform) and the outfit.
    prompt = (
        "Write a short, shareable Instagram/TikTok caption for a thrifted outfit.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Guidelines:\n"
        "- 2 to 4 sentences, casual and authentic like a real OOTD post "
        "(not a product description).\n"
        "- Mention the item name, price, and platform naturally, once each.\n"
        "- Capture the outfit vibe in specific terms.\n"
        "Return only the caption text."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,  # high temperature so captions vary across runs
        )
        caption = (response.choices[0].message.content or "").strip()
    except Exception:
        caption = ""

    # Never return an empty string — fall back to a graceful message.
    if not caption:
        return (
            f"Couldn't generate a fit card for the {new_item['title']} right now — "
            "try again in a moment."
        )

    return caption
