"""Maps an action name to the code that handles it.

This is the seam the next AI capability plugs into. Adding one means writing a
handler and registering it here: authentication, queueing, retries, logging and
cost tracking are already in place around it.
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
