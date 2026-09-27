"""Quick model benchmark for human-like summarisation.

Run from terminal - no pipeline changes needed:

    cd D:\\P&E\\NewsAI
    python benchmark_models.py
    python benchmark_models.py --locale ar
    python benchmark_models.py --locale fr
    python benchmark_models.py --article 3

Prints the output from each model so you can paste it into ZeroGPT,
Qibot, or GPTZero and compare scores.

Also tests the 2-model humaniser approach: generates with Model A,
then rewrites with Model B.
"""

import asyncio
import re
import time
import argparse

import httpx

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

import os; API_KEY = os.environ.get("DEEPINFRA_API_KEY", "")
BASE_URL = "https://api.deepinfra.com/v1/openai"

# Models to benchmark - all commercially licensable
MODELS = {
    "gemma-4-31b": "google/gemma-4-31B-it",
    "qwen3-235b": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "qwen3-32b": "Qwen/Qwen3-32B",
    "deepseek-v4.1-flash": "deepseek-ai/DeepSeek-V4.1-Flash",
    "mistral-small-3.2": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
}

# Sample articles (real published content)
SAMPLE_ARTICLES = {
    "en": {
        1: {
            "title": "HD Construction Equipment and Manitou Partner on Compact Machinery",
            "text": (
                "HD Construction Equipment and Manitou Group have signed a cross-supply "
                "agreement to expand their compact construction equipment portfolios and "
                "strengthen the global offerings of the Hyundai, Develon, Manitou and Gehl "
                "brands. Under the agreement, HD Construction Equipment will source select "
                "compact equipment from Manitou Group to sell under the Hyundai and Develon "
                "brands. In return, Manitou Group will purchase compact equipment from HD "
                "Construction Equipment to sell under the Manitou and Gehl brands. Compact "
                "equipment includes machines such as micro excavators, skid steer loaders "
                "and compact track loaders, which are often used in urban construction, "
                "utilities, landscaping, agriculture and rental sectors. Both companies "
                "bring their existing equipment portfolios to the collaboration. HD "
                "Construction Equipment owns the Hyundai and Develon brands, while Manitou "
                "Group owns Manitou and Gehl, both known for their small machines and "
                "material handling equipment. The collaboration aims to broaden the product "
                "offerings available through both companies' global sales and dealer "
                "networks, as well as to help their development in the compact equipment "
                "space. HD Construction Equipment aims to achieve approximately $930 million "
                "in compact equipment sales by 2030, and the alliance with Manitou is part "
                "of its expansion plan in this category."
            ),
        },
        2: {
            "title": "ROSHN and TMG Plan 55,000-Home Mixed-Use Development in Riyadh",
            "text": (
                "Saudi Arabian real estate developer ROSHN and Egypt's Talaat Moustafa "
                "Group (TMG) have signed a memorandum of understanding to develop a mixed-use "
                "community in Riyadh. The project will include approximately 55,000 homes and "
                "is expected to cover an area of about 20 million square metres. TMG will lead "
                "the master planning and development of the project. ROSHN, a company under "
                "Saudi Arabia's Public Investment Fund, focuses on developing integrated urban "
                "communities across the Kingdom. TMG is one of the largest listed real estate "
                "developers in the Middle East and North Africa. The Riyadh project is part of "
                "Saudi Arabia's wider efforts to increase housing supply and develop new urban "
                "communities. The development is expected to include residential, commercial, "
                "hospitality and recreational components."
            ),
        },
        3: {
            "title": "Caterpillar Delivers First Battery Electric 950 GC Wheel Loader",
            "text": (
                "Caterpillar has delivered the first production unit of its battery electric "
                "950 GC wheel loader to Holcim's Ecllepens quarry in Switzerland. The machine "
                "is part of Caterpillar's expanding lineup of battery electric equipment for "
                "the construction and mining industries. The 950 GC wheel loader is a medium-sized "
                "machine commonly used in quarrying, material handling and general construction. "
                "The battery electric version produces zero direct emissions during operation. "
                "Holcim, a global building materials company, has committed to reducing its CO2 "
                "emissions by 2030 and reaching net zero by 2050. The deployment at Ecllepens "
                "will allow both companies to gather real-world performance data. Caterpillar "
                "said the machine was designed to deliver performance comparable to its diesel "
                "equivalent while eliminating direct exhaust emissions."
            ),
        },
    },
    "ar": {
        1: {
            "title": "Ø´Ø±Ø§ÙƒØ© Ø¨ÙŠÙ† HD Construction Equipment ÙˆÙ…Ø¬Ù…ÙˆØ¹Ø© Ù…Ø§Ù†ÙŠØªÙˆ",
            "text": (
                "Ø£Ø¨Ø±Ù…Øª Ø´Ø±ÙƒØ© HD Construction Equipment ÙˆÙ…Ø¬Ù…ÙˆØ¹Ø© Ù…Ø§Ù†ÙŠØªÙˆ Ø§ØªÙØ§Ù‚ÙŠØ© ØªÙˆØ±ÙŠØ¯ Ù…ØªØ¨Ø§Ø¯Ù„ "
                "Ø¨Ù‡Ø¯Ù ØªÙˆØ³ÙŠØ¹ Ù…Ø­Ø§ÙØ¸ Ù…Ù†ØªØ¬Ø§ØªÙ‡Ù…Ø§ Ù…Ù† Ù…Ø¹Ø¯Ø§Øª Ø§Ù„Ø¨Ù†Ø§Ø¡ Ø§Ù„ØµØºÙŠØ±Ø© ÙˆØªØ¹Ø²ÙŠØ² Ø§Ù„Ø¹Ø±ÙˆØ¶ Ø§Ù„Ø¹Ø§Ù„Ù…ÙŠØ© "
                "Ù„Ù„Ø¹Ù„Ø§Ù…Ø§Øª Ø§Ù„ØªØ¬Ø§Ø±ÙŠØ© Ù‡ÙŠÙˆÙ†Ø¯Ø§ÙŠ ÙˆØ¯ÙŠÙÙŠÙ„ÙˆÙ† ÙˆÙ…Ø§Ù†ÙŠØªÙˆ ÙˆØ¬Ù‡Ù„. ÙˆØ¨Ù…ÙˆØ¬Ø¨ Ù‡Ø°Ù‡ Ø§Ù„Ø§ØªÙØ§Ù‚ÙŠØ©ØŒ "
                "Ø³ØªØ­ØµÙ„ Ø´Ø±ÙƒØ© HD Construction Equipment Ø¹Ù„Ù‰ Ù…Ø¹Ø¯Ø§Øª ØµØºÙŠØ±Ø© Ù…Ø®ØªØ§Ø±Ø© Ù…Ù† Ù…Ø¬Ù…ÙˆØ¹Ø© Ù…Ø§Ù†ÙŠØªÙˆ "
                "Ù„Ø¨ÙŠØ¹Ù‡Ø§ ØªØ­Øª Ø§Ù„Ø¹Ù„Ø§Ù…ØªÙŠÙ† Ø§Ù„ØªØ¬Ø§Ø±ÙŠØªÙŠÙ† Ù‡ÙŠÙˆÙ†Ø¯Ø§ÙŠ ÙˆØ¯ÙŠÙÙŠÙ„ÙˆÙ†. ÙˆÙÙŠ Ø§Ù„Ù…Ù‚Ø§Ø¨Ù„ØŒ Ø³ØªÙ‚ÙˆÙ… Ù…Ø¬Ù…ÙˆØ¹Ø© "
                "Ù…Ø§Ù†ÙŠØªÙˆ Ø¨Ø´Ø±Ø§Ø¡ Ù…Ø¹Ø¯Ø§Øª Ù…Ø¯Ù…Ø¬Ø© Ù…Ù† Ø´Ø±ÙƒØ© HD Construction Equipment ÙˆØ¨ÙŠØ¹Ù‡Ø§ ØªØ­Øª "
                "Ø§Ù„Ø¹Ù„Ø§Ù…ØªÙŠÙ† Ø§Ù„ØªØ¬Ø§Ø±ÙŠØªÙŠÙ† Ù…Ø§Ù†ÙŠØªÙˆ ÙˆØ¬Ù‡Ù„. ØªÙ‡Ø¯Ù Ø´Ø±ÙƒØ© HD Construction Equipment Ø¥Ù„Ù‰ "
                "ØªØ­Ù‚ÙŠÙ‚ Ù…Ø¨ÙŠØ¹Ø§Øª ØªØ¨Ù„Øº Ø­ÙˆØ§Ù„ÙŠ 930 Ù…Ù„ÙŠÙˆÙ† Ø¯ÙˆÙ„Ø§Ø± Ù…Ù† Ø§Ù„Ù…Ø¹Ø¯Ø§Øª Ø§Ù„Ù…Ø¯Ù…Ø¬Ø© Ø¨Ø­Ù„ÙˆÙ„ Ø¹Ø§Ù… 2030."
            ),
        },
    },
    "fr": {
        1: {
            "title": "HD Construction Equipment et Manitou dans les engins compacts",
            "text": (
                "HD Construction Equipment et le Groupe Manitou ont conclu un accord "
                "d'approvisionnement croise visant a elargir leurs gammes de petits engins "
                "de chantier et a renforcer l'offre mondiale des marques Hyundai, Develon, "
                "Manitou et Gehl. Aux termes de cet accord, HD Construction Equipment se "
                "verra fournir par le Groupe Manitou une selection de petits engins qu'elle "
                "commercialisera sous les marques Hyundai et Develon. De son cote, le Groupe "
                "Manitou achetera des engins compacts a HD Construction Equipment pour les "
                "commercialiser sous les marques Manitou et Gehl. HD Construction Equipment "
                "vise a realiser un chiffre d'affaires d'environ 930 millions de dollars "
                "dans le domaine des equipements compacts d'ici 2030."
            ),
        },
    },
}

LANGUAGE = {"en": "English", "ar": "Arabic", "fr": "French"}

# â”€â”€ Prompts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SYSTEM_PROMPT = """You are a trade journalist at a heavy equipment publication, filing a \
brief for the web edition. You write in {language}.

The article below is in {language}. Write a short summary of it in {language}. \
Do not translate it.

Keep it between 2 and 4 sentences, roughly 40 to 100 words. Start with whatever \
happened - the deal, the delivery, the order, the opening.

Get the facts right:
- Names, model codes, figures and prices stay exactly as the article gives them.
- If the article says "about" or "around" or "more than", keep that qualifier.
- Say who did what. When two companies are involved, keep both roles clear.

Write like a reporter, not a press release. Use plain verbs: signed, delivered, \
ordered, will build, opened, bought. Mix up your sentence lengths - a short opener, \
then a longer sentence, then maybe another short one. Do not start every sentence \
the same way.

Write just the summary, nothing else. No heading, no explanation."""

HUMANISE_PROMPT = """You are a native {language} copy editor at a trade magazine.

Below is a short news brief that is factually correct but reads a little stiff.
Rewrite it so it sounds like a real person wrote it quickly at their desk.

Rules:
- Keep every fact, name, number and figure exactly the same.
- Mix up the sentence lengths. One short, one longer, maybe one medium.
- Do not start two sentences the same way.
- Use contractions where natural (English only).
- Keep it the same length (within 10 words).
- Write in {language} only.
- Output ONLY the rewritten text.

Text to rewrite:
{text}"""

# â”€â”€ NLP post-processing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_EN_SWAPS = {
    "utilize": "use", "utilizing": "using", "facilitate": "help",
    "comprehensive": "full", "subsequently": "then",
    "furthermore": "also", "additionally": "also", "demonstrate": "show",
    "significant": "major", "approximately": "about", "enhance": "boost",
    "leverage": "use", "leveraging": "using", "innovative": "new",
    "optimize": "improve", "robust": "strong", "streamline": "simplify",
    "commence": "start", "commenced": "started",
}


def nlp_postprocess(text, locale):
    if locale != "en":
        return text
    changes = 0
    for ai_word, replacement in _EN_SWAPS.items():
        if changes >= 3:
            break
        pattern = re.compile(rf'\b{re.escape(ai_word)}\b', re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub(replacement, text, count=1)
            changes += 1
    for formal, short in [("it is", "it's"), ("do not", "don't")]:
        text = text.replace(formal, short, 1)
        text = text.replace(formal.capitalize(), short.capitalize(), 1)
    return text


# â”€â”€ API call â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def call_model(client, model_id, messages, temperature=0.75, top_p=0.92,
                     freq_penalty=0.3, pres_penalty=0.15, max_tokens=400):
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": freq_penalty,
        "presence_penalty": pres_penalty,
    }
    start = time.monotonic()
    try:
        resp = await client.post("/chat/completions", json=payload)
        elapsed = time.monotonic() - start
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}", elapsed
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        tokens_in = data.get("usage", {}).get("prompt_tokens", 0)
        tokens_out = data.get("usage", {}).get("completion_tokens", 0)
        return text, {"in": tokens_in, "out": tokens_out}, elapsed
    except Exception as e:
        return None, str(e), time.monotonic() - start


# â”€â”€ Benchmark â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def benchmark(locale="en", article_id=1):
    articles = SAMPLE_ARTICLES.get(locale, {})
    if article_id not in articles:
        print(f"No article {article_id} for '{locale}'. Available: {list(articles.keys())}")
        return

    article = articles[article_id]
    language = LANGUAGE[locale]

    print("=" * 80)
    print(f"  MODEL BENCHMARK: Human-Like Output Comparison")
    print(f"  Language: {language}  |  Article #{article_id}: {article['title']}")
    print("=" * 80)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
        {"role": "user", "content": f"<<<ARTICLE>>>\n{article['text']}\n<<<END ARTICLE>>>"},
    ]

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=60.0,
    ) as client:

        results = {}

        # â”€â”€ PART 1: Single model â”€â”€
        print("\n" + "-" * 80)
        print("  PART 1: SINGLE MODEL (Layer 1 only)")
        print("-" * 80)

        for name, model_id in MODELS.items():
            print(f"\n  >>> {name}")
            text, meta, elapsed = await call_model(client, model_id, messages)
            if text is None:
                print(f"      ERROR: {meta}")
                continue
            results[name] = text
            print(f"      Time: {elapsed:.1f}s | Words: {len(text.split())} | Tokens: {meta}")
            print()
            print(text)
            print()

        # â”€â”€ PART 2: Two-model + NLP â”€â”€
        print("-" * 80)
        print("  PART 2: TWO-MODEL + NLP (All 3 Layers)")
        print("-" * 80)

        for name, raw_text in results.items():
            if name == "deepseek-v4.1-flash":
                h_id = "Qwen/Qwen3-235B-A22B-Instruct-2507"
                h_name = "qwen3-235b"
            else:
                h_id = "deepseek-ai/DeepSeek-V4.1-Flash"
                h_name = "deepseek-v4.1-flash"

            h_messages = [{"role": "user", "content": HUMANISE_PROMPT.format(
                language=language, text=raw_text
            )}]

            h_text, _, h_elapsed = await call_model(
                client, h_id, h_messages,
                temperature=0.85, top_p=0.95, freq_penalty=0.4, pres_penalty=0.2,
            )
            if h_text is None:
                print(f"\n  >>> {name} -> {h_name}: FAILED")
                continue

            final = nlp_postprocess(h_text, locale)
            print(f"\n  >>> {name} -> {h_name} (3 layers)")
            print(f"      Time: {h_elapsed:.1f}s | Words: {len(final.split())}")
            print()
            print(final)
            print()

        print("=" * 80)
        print("  COPY EACH OUTPUT AND PASTE INTO:")
        print("    https://www.zerogpt.com/")
        print("    https://gptzero.me/")
        print("    https://qibot.ai/")
        print()
        print("  Best single model = PRIMARY model")
        print("  Best 2-model combo = PRODUCTION setup")
        print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", default="en", choices=["en", "ar", "fr"])
    parser.add_argument("--article", type=int, default=1, choices=[1, 2, 3])
    asyncio.run(benchmark(locale=parser.parse_args().locale,
                           article_id=parser.parse_args().article))
