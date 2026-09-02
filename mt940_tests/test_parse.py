import os
import pathlib
import pickle

import mt940
import pytest

_tests_path = pathlib.Path(__file__).parent
_ING = _tests_path / 'jejik' / 'ing.sta'


@pytest.mark.parametrize(
    ('path', 'encoding'),
    [
        (_ING, 'utf-8'),
        (_tests_path / 'self-provided' / 'raphaelm.sta', 'utf-8'),
        (_tests_path / 'betterplace' / 'with_binary_character.sta', 'utf-8'),
    ],
)
def test_non_ascii_parse(path: pathlib.Path, encoding: str) -> None:
    # Read as binary
    with path.open('rb') as fh:
        data = fh.read().decode(encoding)
        _ = pickle.dumps(mt940.parse(data))

    # Read as text
    with path.open('r', encoding=encoding) as fh:
        _ = pickle.dumps(mt940.parse(fh.read()))


_BOM_STATEMENT = (
    ':20:REF\n'
    ':25:NL00BANK0123456789\n'
    ':28C:1/1\n'
    ':60F:C091019EUR1000,00\n'
    ':61:0910201020C500,00NTRFNONREF//B\n'
    ':86:Example transaction\n'
    ':62F:C091020EUR1500,00\n'
)
_ACCENTED_STATEMENT = _BOM_STATEMENT.replace(
    'Example transaction', 'Café transaction'
)


def test_utf8_bom_bytes_does_not_drop_first_tag() -> None:
    # A UTF-8 BOM (emitted by many Windows tools/banks) must not push the
    # leading :20: past the start-of-line tag anchor and drop its data.
    data = b'\xef\xbb\xbf' + _BOM_STATEMENT.encode('utf-8')
    transactions = mt940.parse(data)
    assert transactions.data.get('transaction_reference') == 'REF'
    assert len(transactions) == 1


def test_utf8_bom_str_does_not_drop_first_tag() -> None:
    # Same file already decoded to str with a stray BOM character.
    transactions = mt940.parse('﻿' + _BOM_STATEMENT)
    assert transactions.data.get('transaction_reference') == 'REF'
    assert len(transactions) == 1


def test_string_that_is_not_a_path_is_parsed_as_data() -> None:
    transactions = mt940.parse(_BOM_STATEMENT)
    assert transactions.data['transaction_reference'] == 'REF'
    assert transactions[0].data['transaction_details'] == 'Example transaction'


def test_bytes_path_parses_like_a_str_path() -> None:
    # os.path accepts bytes paths, so the parser does too.
    from_str = mt940.parse(str(_ING))
    from_bytes = mt940.parse(os.fsencode(_ING))
    assert len(from_bytes) == len(from_str)
    assert from_bytes.data == from_str.data


def test_missing_path_like_source_raises() -> None:
    # A str that is not a file is statement data. A path-like object cannot
    # be, so a missing one is an error rather than an empty parse.
    with pytest.raises(FileNotFoundError, match=r'statement\.sta'):
        _ = mt940.parse(pathlib.Path('/nonexistent/statement.sta'))


def test_explicit_encoding_is_tried_first() -> None:
    data = _ACCENTED_STATEMENT.encode('cp1252')
    transactions = mt940.parse(data, encoding='cp1252')
    assert transactions[0].data['transaction_details'] == 'Café transaction'


def test_invalid_utf8_falls_back_to_cp852() -> None:
    # 0xE9 is a lone continuation byte in UTF-8, so the UTF-8 attempt fails
    # and cp852, which maps every byte value, decodes it (to a different
    # character than cp1252 would, which is why encoding= exists).
    data = _ACCENTED_STATEMENT.encode('cp1252')
    transactions = mt940.parse(data)
    expected = 'Café transaction'.encode('cp1252').decode('cp852')
    assert transactions[0].data['transaction_details'] == expected


_LOOKALIKE_STATEMENT = """:20:R
:25:A
:28C:1
:60F:C240101EUR0,00
:61:2401010101C10,00NTRFREF//B
:86:PAYMENT FOR
:12:INVOICE STYLE REF
:62F:C240101EUR10,00
"""


def test_86_line_with_embedded_tag_lookalike_stays_in_details() -> None:
    # A :86: free-text line that itself starts with a tag-lookalike (:12:,
    # which is not a known tag) must not be split off as a separate tag and
    # corrupt the statement. It stays part of the transaction details.
    transactions = mt940.parse(_LOOKALIKE_STATEMENT)
    assert len(transactions) == 1
    # No corruption: the closing balance still parses off the real :62F:.
    assert (
        str(transactions.data['final_closing_balance'].amount) == '10.00 EUR'
    )
    # The lookalike line is retained verbatim inside the details.
    details = transactions[0].data['transaction_details']
    assert 'INVOICE STYLE REF' in details


def test_parse_statements_drops_swift_header_and_absorbs_terminators() -> None:
    # A leading SWIFT {1:}{2:}{4: header before the first :20: must be dropped,
    # and the lone `-` statement terminators must not create empty statements.
    data = """{1:F01BANKNL2AXXXX0000000000}{2:I940BANKNL2AXXXXN}{4:
:20:STMT1
:25:NL00BANK1
:28C:1/1
:60F:C240101EUR100,00
:62F:C240101EUR100,00
-}
:20:STMT2
:25:NL00BANK2
:28C:2/1
:60F:C240102EUR200,00
:62F:C240102EUR200,00
-
"""
    statements = mt940.parse_statements(data)
    assert [s.data['transaction_reference'] for s in statements] == [
        'STMT1',
        'STMT2',
    ]


_INDENTED_STATEMENT = """:20:R
:25:A
:28C:1
:60F:C240101EUR0,00
:61:2401010101C10,00NTRFREF//B
:86:LINE ONE
    INDENTED TWO
:62F:C240101EUR10,00
"""


def test_86_continuation_preserves_leading_whitespace() -> None:
    # Transactions.strip only rstrips, so significant leading whitespace on a
    # :86: continuation line is preserved rather than eaten.
    transactions = mt940.parse(_INDENTED_STATEMENT)
    assert transactions[0].data['transaction_details'] == (
        'LINE ONE\n    INDENTED TWO'
    )


def test_pickle_roundtrip_restores_processors() -> None:
    # __getstate__ drops the (unpicklable) processors. __setstate__ must
    # restore them so the unpickled object is still usable.
    with _ING.open(encoding='utf-8') as fh:
        transactions = mt940.parse(fh.read())

    # Trusted, self-produced pickle (a round-trip of our own object), so
    # pickle.loads is safe here.
    restored = pickle.loads(pickle.dumps(transactions))

    assert restored.processors == transactions.processors
    assert len(restored) == len(transactions)
    # Re-parsing exercises the restored processors without raising, and
    # parse() hands back the accumulated transactions.
    assert len(restored.parse('')) == len(transactions)


def test_pickle_roundtrip_preserves_transaction_boundary() -> None:
    # __getstate__ only drops `processors`. Newer state such as the opt-in
    # `transaction_boundary` (issue #110) must survive a pickle round-trip.
    transactions = mt940.models.Transactions(
        transaction_boundary={'transaction_reference_number'}
    )

    # Trusted, self-produced pickle (a round-trip of our own object), so
    # pickle.loads is safe here.
    restored = pickle.loads(pickle.dumps(transactions))

    assert restored.transaction_boundary == frozenset({
        'transaction_reference_number'
    })
