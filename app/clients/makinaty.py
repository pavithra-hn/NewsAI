"""Talks to MakinatyNews. The only module that knows its payload shapes."""

from dataclasses import dataclass

import httpx

from app.config import SUPPORTED_LOCALES, settings


class ArticleNotFound(Exception):
    def __init__(self, article_id: int) -> None:
        super().__init__(f"Article {article_id} not found")
        self.article_id = article_id


class ArticleFetchFailed(Exception):
    pass


@dataclass(frozen=True)
class Article:
    article_id: int
    locale: str
    body_html: str
    title: str | None = None


def _validate_article_id(article_id) -> int:
    # The id goes into a URL, so it is checked rather than trusted. bool is a
    # subclass of int and is not an article id.
    if isinstance(article_id, bool) or not isinstance(article_id, int):
        raise TypeError(f"article_id must be an int, got {type(article_id).__name__}")
    if article_id < 1:
        raise ValueError(f"article_id must be positive, got {article_id}")
    return article_id


def _validate_locale(locale) -> str:
    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"unsupported locale: {locale!r}")
    return locale


class MakinatyClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url or settings.makinaty_base_url,
            timeout=timeout or settings.makinaty_timeout_seconds,
            headers={
                "Authorization": f"Bearer {token or settings.outbound_api_token}"
            },
            # A redirect to another host would carry our bearer token there.
            follow_redirects=False,
        )

    async def fetch_article(self, article_id, locale) -> Article:
        article_id = _validate_article_id(article_id)
        locale = _validate_locale(locale)

        try:
            response = await self._client.get(
                f"/article/{article_id}", params={"locale": locale}
            )
        except httpx.HTTPError as exc:
            raise ArticleFetchFailed(str(exc)) from exc

        if response.is_redirect:
            raise ArticleFetchFailed(
                f"refused redirect to {response.headers.get('Location')!r}"
            )
        if response.status_code == 404:
            raise ArticleNotFound(article_id)
        if response.status_code >= 400:
            raise ArticleFetchFailed(f"{response.status_code} from MakinatyNews")

        payload = response.json()
        return Article(
            article_id=article_id,
            locale=locale,
            # A locale with no text arrives as null. Coercing it here lets the
            # pre-flight check own that outcome instead of clean() raising.
            body_html=payload.get("description") or "",
            title=payload.get("title"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
