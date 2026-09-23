"""Maps an action name to the code that handles it.

This is the seam the next AI capability plugs into: write a handler and register
it here. The HTTP API, authentication and job queue that will dispatch to these
handlers arrive with the API work; today only the CLI calls them.
"""

from collections.abc import Awaitable, Callable

from app.actions.quick_read import handle as quick_read

ACTIONS: dict[str, Callable[..., Awaitable]] = {
    "quick_read": quick_read,
}


def get_action(name: str) -> Callable[..., Awaitable]:
    try:
        return ACTIONS[name]
    except KeyError:
        raise KeyError(f"unknown action: {name!r}. Known actions: {sorted(ACTIONS)}") from None
