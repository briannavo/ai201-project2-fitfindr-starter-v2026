"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import config
from generate import generate
from utils.data_loader import load_listings
import re

# ── Tool 1: search_listings ───────────────────────────────────────────────────

_STOPWORDS = {
    # articles, conjunctions, prepositions
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet",
    "for", "with", "without", "under", "over", "in", "of", "on", "at", "to",
    "from", "by", "about", "into", "onto", "than", "as", "like",
    # pronouns and determiners
    "i", "i'm", "im", "me", "my", "mine", "myself", "we", "us", "our",
    "you", "your", "it", "its", "it's", "this", "that", "these", "those",
    "some", "any", "something", "anything", "one", "ones", "each", "every",
    # common verbs and auxiliaries
    "is", "are", "was", "were", "be", "been", "being", "am",
    "do", "does", "did", "have", "has", "had", "can", "could", "would",
    "should", "will", "shall", "may", "might", "must",
    # request / search filler
    "want", "wanna", "need", "looking", "look", "find", "finding", "search",
    "searching", "show", "get", "give", "buy", "please", "pls", "help",
    "hi", "hey", "hello", "thanks", "thank",
    # vague qualifiers
    "very", "really", "just", "maybe", "kind", "kinda", "sort", "sorta",
    "type", "ish", "also", "too", "only", "even", "pretty", "quite",
    "good", "nice", "great", "cool",
    # price and size filler (handled by the size / max_price filters)
    "size", "sized", "price", "priced", "cost", "costs", "budget",
    "dollar", "dollars", "bucks", "usd", "cheap", "cheaper", "affordable",
}

def _keywords(text: str) -> set[str]:
    """Lowercase words worht matching on, stopwords removed. """
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}

def _size_tokens(size: str) -> set[str]:
    cleaned = re.sub(r"\([^)]*\)", " ", size or "") # drop parentheticals
    parts = [p.strip().upper() for p in cleaned.split("/")]
    return {p for p in parts if p}

def _size_matches(wanted: str, listing_size: str) -> bool:
    if not wanted:
        return True
    listing_tokens = _size_tokens(listing_size)
    if any(token.startswith("ONE SIZE") for token in listing_tokens):
        return True
    return bool(_size_tokens(wanted) & listing_tokens)

def _listing_keywords(listing: dict) -> set[str]:
    """Keywords from every text field of a listing. brand may be None."""
    text = " ".join([
        listing.get("title") or "",
        listing.get("description") or "",
        listing.get("category") or "",
        " ".join(listing.get("style_tags") or []),
        " ".join(listing.get("colors") or []),
        listing.get("brand") or "",
    ])
    return _keywords(text)

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    listings = load_listings()

    if max_price is not None:
        listings = [l for l in listings if float(l.get("price", 0)) <= max_price]

    if size:
        listings = [l for l in listings if _size_matches(size, l.get("size", ""))]

    query = _keywords(description)
    if not query:
        return []

    scored = []
    for listing in listings:
        score = len(query & _listing_keywords(listing))
        if score > 0:
            scored.append((score, listing))

    # sorted() is stable, so ties keep their dataset order
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in scored[:config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _describe_item(item: dict) -> str:
    """A listing as prompt-ready lines. Skips fields that are missing or None."""
    price = item.get("price")
    lines = [
        f"Title: {item.get('title', 'Unknown item')}",
        f"Category: {item.get('category')}" if item.get("category") else "",
        f"Description: {item.get('description')}" if item.get("description") else "",
        f"Colors: {', '.join(item['colors'])}" if item.get("colors") else "",
        f"Style: {', '.join(item['style_tags'])}" if item.get("style_tags") else "",
        f"Size: {item.get('size')}" if item.get("size") else "",
        f"Condition: {item.get('condition')}" if item.get("condition") else "",
        f"Brand: {item.get('brand')}" if item.get("brand") else "",
        f"Price: ${float(price):.2f}" if price is not None else "",
        f"Platform: {item.get('platform')}" if item.get("platform") else "",
    ]
    return "\n".join(line for line in lines if line)

def _describe_wardrobe_item(item: dict) -> str:
    """One wardrobe piece as a single bullet line."""
    parts = [item.get("name", "unnamed piece")]
    if item.get("category"):
        parts.append(item["category"])
    if item.get("colors"):
        parts.append(", ".join(item["colors"]))
    if item.get("style_tags"):
        parts.append(", ".join(item["style_tags"]))
    line = "- " + " | ".join(parts)
    if item.get("notes"):
        line += f" (note: {item['notes']})"
    return line

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    items = (wardrobe or {}).get("items") or []
    item_text = _describe_item(new_item)

    system = (
        "You are a friendly thrift stylist. Give practical, specific outfit "
        "ideas in plain text. Keep it to one or two outfits, a few lines each."
    )

    if not items:
        prompt = (
            f"Someone is thinking about buying this thrifted piece:\n{item_text}\n\n"
            "They haven't told us what's in their wardrobe. Suggest one or two "
            "outfits built around this piece using common staples (say what "
            "kind of bottoms, shoes, layers, accessories), and say what vibe "
            "each outfit gives."
        )
    else:
        wardrobe_text = "\n".join(_describe_wardrobe_item(w) for w in items)
        prompt = (
            f"Someone is thinking about buying this thrifted piece:\n{item_text}\n\n"
            f"Here is what they already own:\n{wardrobe_text}\n\n"
            "Suggest one or two outfits that pair the new piece with specific "
            "items from their wardrobe. Name the wardrobe pieces you use exactly "
            "as listed. Only use pieces from the list. If something is missing "
            "(like shoes), say what kind would work."
        )

    response = generate(prompt, system=system).strip()
    if not response:
        return (
            f"No outfit ideas came back for the {new_item.get('title', 'item')}. "
            "Try again in a moment."
        )
    return response


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip():
        return (
            "Can't write a fit card without an outfit. Get an outfit suggestion "
            "for this item first, then try again."
        )

    system = (
        "You write short, casual social media captions about thrift finds. "
        "Sound like a real person posting their outfit, not a product listing. "
        "No hashtag walls; one or two hashtags at most, or none."
    )
    prompt = (
        f"The thrifted item:\n{_describe_item(new_item)}\n\n"
        f"The outfit it's styled in:\n{outfit.strip()}\n\n"
        "Write a caption of two to four sentences. Mention the item, its price, "
        "and the platform it came from exactly once each. Be specific about "
        "the vibe of the outfit. Return only the caption."
    )

    response = generate(prompt, system=system).strip()
    if not response:
        return (
            f"Couldn't write a caption for the {new_item.get('title', 'item')} "
            "this time. Try again in a moment."
        )
    return response
