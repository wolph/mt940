import pytest

from mt940 import utils


@pytest.mark.parametrize('input_,flags,output', [
    (' a \n b ', None, 'ab'),
    (' a \n b ', utils.Strip.LEFT, 'a b '),
    (' a \n b ', utils.Strip.RIGHT, ' a b'),
    (' a \n b ', utils.Strip.NONE, ' a  b '),

])
def test_join_lines(input_, flags, output):
    if flags is None:
        assert utils.join_lines(input_) == output
    else:
        assert utils.join_lines(input_, flags) == output
