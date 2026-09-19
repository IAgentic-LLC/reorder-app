"""Chapter 26: a rotation boundary is the line in an architecture where
a secret's own lifecycle, issued, active, rotated, revoked, is decoupled
from a process's own lifecycle. For this app, that line runs right
through `os.environ` itself: a lazy read inside a function (chapter 6's
own fix) solves an import-order bug, it does not make a running
process see a value the operating system handed it once, at process
start, differently later. `fly secrets set` only works because Fly's
own rolling restart replaces the process entirely; nothing here would
help this exact same code running under a supervisor that never
restarts it.

`secret_digest` never returns a real secret value, only a short hash,
safe to expose behind auth as a way to answer a real operational
question: has this specific running machine actually picked up a
rotation yet, or is it still serving the previous release.
"""

import hashlib
import os
import time

_PROCESS_STARTED_AT = time.time()


def secret_digest() -> str:
    material = "|".join(
        [
            os.environ.get("GEMINI_API_KEY", ""),
            os.environ.get("DATABASE_URL", ""),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def process_started_at() -> float:
    return _PROCESS_STARTED_AT
