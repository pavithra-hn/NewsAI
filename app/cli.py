"""Runs one article through the pipeline and prints what came back.

    python -m app.cli --article 1 --locale ar

Development entry point, not a production interface. The HTTP API arrives with
the API card. This exists so output can be read by a person while the prompt
and the checks are being tuned.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.actions.registry import get_action
from app.clients.makinaty import Article, MakinatyClient
from app.config import SUPPORTED_LOCALES, settings
from app.pipeline.clean import clean
from app.providers.llm import LLMProvider

CORPUS_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "corpus.json"


class CorpusClient:
    """Serves articles from the committed corpus instead of MakinatyNews.

    The 25 articles are real and already published, so development runs send
    nothing unpublished to a provider.
    """

    def __init__(self, path: Path = CORPUS_PATH) -> None:
        self.articles = json.loads(path.read_text(encoding="utf-8"))

    def check_range(self, article_id: int) -> None:
        # Without this, article 0 reads index -1 and silently returns the
        # last article in the corpus.
        if not 1 <= article_id <= len(self.articles):
            raise ValueError(
                f"article must be between 1 and {len(self.articles)}, got {article_id}"
            )

    async def fetch_article(self, article_id: int, locale: str) -> Article:
        self.check_range(article_id)
        version = self.articles[article_id - 1]["locales"][locale]
        return Article(
            article_id=article_id,
            locale=locale,
            body_html=version["body_html"],
            title=version["title"],
        )


def report(result, seconds: float, source_words: int) -> None:
    print()
    print(f"  article   {result.article_id}   locale {result.locale}   model {result.model}")
    print(f"  source    {source_words} words")
    print()
    print("  quick read")
    print(f"    {result.text or '(nothing returned)'}")
    print()
    print(f"  words     {len(result.text.split())}")
    print(f"  time      {seconds:.2f}s")

    # A model with no published rate has no known cost. Printing $0 for it
    # would report spend that was never measured.
    cost = f"${result.cost_usd:.6f}" if result.cost_known else "unknown, model is not priced"
    print(f"  cost      {cost}")

    hard = ", ".join(f"{f.code}" for f in result.checks.hard) or "none"
    soft = ", ".join(f"{w.code}" for w in result.checks.soft) or "none"
    print(f"  hard      {hard}")
    print(f"  soft      {soft}")
    print(f"  deliver   {'yes' if result.deliverable else 'NO'}", end="")
    print(f"   review {'yes' if result.needs_review else 'no'}")
    print()


async def run(article_id: int, locale: str, live: bool) -> int:
    client = MakinatyClient() if live else CorpusClient()
    provider = LLMProvider()

    article = await client.fetch_article(article_id, locale)
    source_words = len(clean(article.body_html).split())

    started = time.monotonic()
    try:
        result = await get_action("quick_read")(article_id, locale, client=client, provider=provider)
    finally:
        await provider.aclose()
    elapsed = time.monotonic() - started

    report(result, elapsed, source_words)
    return 0 if result.deliverable else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article", type=int, required=True, help="1-based corpus position")
    parser.add_argument("--locale", required=True, choices=sorted(SUPPORTED_LOCALES))
    parser.add_argument(
        "--live",
        action="store_true",
        help="fetch from MakinatyNews instead of the committed corpus",
    )
    args = parser.parse_args(argv)

    if not args.live:
        try:
            CorpusClient().check_range(args.article)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2

    if not settings.provider_api_key:
        print("PROVIDER_API_KEY is not set. Put it in .env or the environment.", file=sys.stderr)
        return 2

    return asyncio.run(run(args.article, args.locale, args.live))


if __name__ == "__main__":
    raise SystemExit(main())
