# FitFindr

FitFindr is a thrift-styling agent: you describe a secondhand piece in natural
language, and it searches a mock listings dataset, picks the best match, styles
it against your wardrobe, and writes a shareable "fit card" caption — all in one
pass through a fixed planning loop.

## Tools

The agent uses three required tools, each a standalone function in
[tools.py](tools.py).

### `search_listings(description, size, max_price) -> list[dict]`
Searches the listings dataset for items matching the description, optional size,
and optional price ceiling.

**Inputs:**
- `description` (str): keywords describing what the user is looking for.
- `size` (str | None): size string to filter by, or `None` to skip the size
  filter. Matching is case-**in**sensitive (e.g. `"m"` matches `"S/M"`).
- `max_price` (float | None): maximum price (**in**clusive), or `None` to skip
  the price filter.

**Returns:** a `list[dict]` of matching listings, sorted by relevance (best match
first). Relevance is a score = the number of keywords from `description`
(lowercased, split on whitespace) that appear in the listing's
title + description + style_tags; listings scoring 0 are dropped and ties are
broken by lower price. Each listing dict has the keys: `id` (str), `title` (str),
`description` (str), `category` (str: tops/bottoms/outerwear/shoes/accessories),
`style_tags` (list[str]), `size` (str), `condition` (str: excellent/good/fair),
`price` (float), `colors` (list[str]), `brand` (str or None), `platform`
(str: depop/thredUp/poshmark).

**On failure / no match:** returns an empty list — does **not** raise an exception.

### `suggest_outfit(new_item, wardrobe) -> str`
Given a thrifted item and the user's wardrobe, suggests 1–2 complete outfits via
the Groq LLM.

**Inputs:**
- `new_item` (dict): a listing dict (the item the user is considering buying),
  with the keys listed above.
- `wardrobe` (dict): a wardrobe dict with an `items` key holding a list of
  wardrobe-item dicts; each has `id`, `name` (str), `category`, `colors`
  (list[str]), `style_tags` (list[str]), `notes` (str or None). May be empty.

**Returns:** a non-empty string with outfit suggestions. When the wardrobe is
non-empty it references pieces by name; when empty it offers general styling
advice for the item.

**On failure:** if the wardrobe is empty it gives general advice rather than
failing; if the LLM call errors or returns nothing, it returns a graceful
fallback string instead of raising or returning `""`.

### `create_fit_card(outfit, new_item) -> str`
Generates a short, shareable OOTD caption for the thrifted find (~2–4 sentences,
mentioning the item title, price, and platform once each; higher LLM temperature
so output varies).

**Inputs:**
- `outfit` (str): the outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict): the listing dict for the thrifted item.

**Returns:** a 2–4 sentence string usable as an Instagram/TikTok caption.

**On failure:** if `outfit` is empty or whitespace-only, returns a descriptive
error string — does **not** raise. If the LLM call errors or returns nothing, it
returns a graceful fallback string.

## Planning Loop

The loop ([`run_agent`](agent.py) in [agent.py](agent.py)) is a **fixed
sequential pipeline, not an intent classifier**. It runs every stage in order,
passing state through the session dict, and branches only on failure:

1. **Initialize** `session = _new_session(query, wardrobe)`.
2. **Parse** the query into `description`, `size`, `max_price` (regex +
   string-splitting, deterministic) and store it in `session["parsed"]`.
   **Branch:** if no usable description is extracted, set
   `session["error"] = "I couldn't tell what you're looking for — try describing the item."`
   and return immediately (search never runs).
3. **Search:** `results = search_listings(...)`, stored in
   `session["search_results"]`. **Branch:** if `results == []`, set
   `session["error"] = "No listings matched — try removing the size or raising your price."`
   and return immediately — `suggest_outfit` is **not** called with empty input.
4. **Select:** `session["selected_item"] = results[0]` (top-ranked match).
5. **Suggest:** `session["outfit_suggestion"] = suggest_outfit(selected_item, wardrobe)`.
   Guarded: an empty/whitespace result sets `session["error"]` and returns.
6. **Caption:** `session["fit_card"] = create_fit_card(outfit, selected_item)`
   (always a string — stored as-is).
7. **Return** the session. Success means `session["error"]` is `None`.

The conditional logic keys off **what each stage wrote to the session**: an
unparseable query short-circuits at Step 2, a zero-result search short-circuits
at Step 3, and only a non-empty result set flows into the LLM-backed styling
stages. Two different bad inputs therefore produce two different error messages
rather than one fixed sequence of tool calls.

## State Management

State lives in a single **session dict** created by `_new_session()`
([agent.py](agent.py)). It is the single source of truth for one interaction and
tracks: `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`,
`outfit_suggestion`, `fit_card`, and `error`.

Each stage reads the field the previous stage wrote and writes its own result
back, so data flows tool-to-tool **without the user re-entering anything**:

```
parsed → search_results → selected_item → outfit_suggestion → fit_card
```

Concretely, `search_listings`'s top result is stored as
`session["selected_item"]` and passed straight into `suggest_outfit`; that
function's return is stored as `session["outfit_suggestion"]` and passed straight
into `create_fit_card`. Setting `session["error"]` short-circuits the remaining
stages.

## Error Handling

Each tool handles a specific failure mode and never raises into the loop:

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listing matches the query | Returns an empty list; the loop sets `session["error"]` ("No listings matched — try removing the size or raising your price.") and stops before the LLM tools. |
| `suggest_outfit` | Wardrobe is empty, or the LLM call errors / returns nothing | Empty wardrobe → general styling advice; LLM failure → graceful fallback string ("Couldn't generate outfit ideas … try again in a moment."). Never raises or returns `""`. |
| `create_fit_card` | `outfit` is empty / missing, or the LLM call errors | Empty outfit → descriptive error string ("Can't write a fit card without an outfit suggestion — run suggest_outfit() first."). Never raises. |

**Concrete example from testing:** in
[tests/test_tools.py](tests/test_tools.py), `test_suggest_outfit_survives_llm_failure`
monkeypatches `_get_groq_client` to raise `RuntimeError("API down")`; the tool
catches it and returns a non-empty fallback string instead of crashing.
Similarly, `test_create_fit_card_empty_outfit_returns_error` calls
`create_fit_card("", item)` and asserts a descriptive error string is returned
rather than an exception.

## Spec Reflection

**One way the spec helped:** writing the Tool 1 block in `planning.md` first —
inputs (`description`/`size`/`max_price`), the `list[dict]` return, the
keyword-overlap relevance definition, and the empty-list failure mode — gave
Claude a precise contract to implement against, so `search_listings` matched the
intended behavior on the first pass and the tests could assert on exact,
deterministic results.

**One divergence and why:** the planned query parser used the *whole* query as
the search description. In practice that leaked wardrobe context like "I mostly
wear baggy jeans" into the search keywords and skewed relevance scoring, so I
diverged from the plan and built the description from only the **first sentence**
while still pulling price and size from the full text (see `_parse_query` in
[agent.py](agent.py)).

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

## AI Usage

I used **Claude (via Claude Code)** as a coding assistant throughout this project. For each piece I gave it a specific section of `planning.md` as the spec, reviewed what it produced against that spec, and changed anything that didn't match before trusting it.

For example: I gave Claude the **Tool 1 block** (the `description`/`size`/`max_price` inputs, the `list[dict]` return, my relevance definition, and the empty-list failure mode) plus the `load_listings()` docstring, and it produced the keyword-overlap scoring loop in `search_listings()` — but I caught that my first price-filter test passed *vacuously* (`max_price=10` matched nothing, so `all(...)` over an empty list was trivially true), so I raised the ceiling and added real size-filter and sort-order tests. For the **planning loop**, I gave Claude the Planning Loop section (Steps 1–7 with both early-return branches) and the architecture diagram, and it produced the query parser plus the seven-step `run_agent()` loop; its first parser used the whole query as the search description, which leaked wardrobe context like *"I mostly wear baggy jeans"* into the search keywords, so I overrode it to build the description from only the first sentence while still pulling price and size from the full text.
