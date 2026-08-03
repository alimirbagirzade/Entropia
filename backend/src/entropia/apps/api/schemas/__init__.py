"""Published response contracts for the HTTP surface.

A route that returns a bare ``dict[str, Any]`` keeps its response body INVISIBLE to
``docs/openapi.json`` while the drift guard stays green — the trap O-30 closed for the
purge 202 and G-02 closed for the package export. These modules hold the response models
that make those bodies part of the published schema instead.

Why here and not in the route module (the O-30 / G-02 precedent): the route modules state
in their own docstrings that they are THIN handlers. Typing three surfaces at once adds
~40 models; inlining them would push ``routes/library.py`` past 550 lines and bury the
handlers. The models stay one-per-surface here and the routes import them by name.

Two rules hold for every model in this package:

* **No field is dropped.** ``response_model`` filters the body to the declared fields, so a
  key the serializer emits but the model omits disappears silently. Each model mirrors one
  serializer function key-for-key and is pinned by a no-field-drop regression test.
* **Every field is REQUIRED; nullability lives in the TYPE.** ``x: str | None`` (no
  default) keeps the key present in ``required`` and lets the value be ``null`` — which is
  what the wire actually does and what the frontend interfaces already declare. A
  ``= None`` default would advertise an omittable key that is never omitted.

Enums are declared ``str``, not the Python enum: the serializers already emit the lowercase
``StrEnum`` value, and publishing a closed enum would turn any new member into a 500 on a
response that is otherwise valid. Datetimes are declared ``str`` for the same reason — the
serializers emit ``.isoformat()`` and re-parsing to ``datetime`` would re-render the value.
"""

from __future__ import annotations
