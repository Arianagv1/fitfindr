# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

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
