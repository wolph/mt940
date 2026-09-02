import json

import mt940
import pytest


def test_default_rejects_unknown_objects() -> None:
    # Anything the encoder does not know is handed to the stdlib default,
    # which refuses it instead of guessing.
    with pytest.raises(TypeError, match='not JSON serializable'):
        _ = mt940.JSONEncoder().default(object())


def test_dumps_rejects_unknown_objects() -> None:
    with pytest.raises(TypeError, match='not JSON serializable'):
        _ = json.dumps({'value': object()}, cls=mt940.JSONEncoder)
