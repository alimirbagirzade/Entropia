"""General Dramatiq worker plane entrypoint package.

Importing this package imports the actor module, which first installs the broker
and then registers all known actors so the Dramatiq CLI can discover them.
Domain actors arrive Stage 1+; Stage 0 ships a single system heartbeat actor.
"""

from entropia.apps.worker import actors  # noqa: F401  (installs broker + registers actors)
