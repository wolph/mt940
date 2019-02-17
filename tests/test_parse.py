import pytest
import mt940


@pytest.mark.parametrize('filename,encoding', [
    # ('tests/jejik/ing.sta', 'utf-8'),
    # ('tests/self-provided/raphaelm.sta', 'utf-8'),
    ('tests/betterplace/with_binary_character.sta', 'utf-8'),
])
def test_non_ascii_parse(filename, encoding):
    # Read as binary
    with open(filename, 'rb') as fh:
        data = fh.read()
        data = data.decode(encoding)
        mt940.parse(data)

    # Read as text
    with open(filename, 'r') as fh:
        data = fh.read()
        mt940.parse(data)

