import pathlib
import pickle

import mt940
import pytest

_tests_path = pathlib.Path(__file__).parent


@pytest.mark.parametrize(
    'path,encoding',
    [
        (_tests_path / 'jejik' / 'ing.sta', 'utf-8'),
        (_tests_path / 'self-provided' / 'raphaelm.sta', 'utf-8'),
        (_tests_path / 'betterplace' / 'with_binary_character.sta', 'utf-8'),
    ],
)
def test_non_ascii_parse(path, encoding):
    # Read as binary
    with path.open('rb') as fh:
        data = fh.read()
        data = data.decode(encoding)
        pickle.dumps(mt940.parse(data))

    # Read as text
    with path.open('r') as fh:
        data = fh.read()
        pickle.dumps(mt940.parse(data))
