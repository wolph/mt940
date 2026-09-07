import contextlib
import os
import pathlib
import pickle
import typing
from collections.abc import Iterable

import mt940
import mt940._types
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


_BOM_BYTES = b'\xef\xbb\xbf' + _BOM_STATEMENT.encode('utf-8')


@pytest.mark.parametrize(
    'data', [_BOM_BYTES, '﻿' + _BOM_STATEMENT], ids=['bytes', 'str']
)
def test_bom_drops_the_first_tag_by_default(data: bytes | str) -> None:
    # 5.0.0 kept a leading BOM. It is not whitespace, so it pushes the
    # leading :20: past the start-of-line tag anchor and that tag's data is
    # lost, and parse_statements finds no statement at all.
    transactions = mt940.parse(data)
    assert 'transaction_reference' not in transactions.data
    assert len(transactions) == 1
    assert mt940.parse_statements(data) == []


@pytest.mark.parametrize(
    'data', [_BOM_BYTES, '﻿' + _BOM_STATEMENT], ids=['bytes', 'str']
)
def test_strip_bom_option_keeps_the_first_tag(data: bytes | str) -> None:
    # A UTF-8 BOM (emitted by many Windows tools/banks) is dropped on
    # request, and the :20: parses.
    options = mt940.Options(strip_bom=True)
    transactions = mt940.parse(data, options=options)
    assert transactions.data.get('transaction_reference') == 'REF'
    assert len(transactions) == 1
    statements = mt940.parse_statements(data, options=options)
    assert [s.data['transaction_reference'] for s in statements] == ['REF']


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
    # be, so a missing one is an error rather than an empty parse. 5.0.0
    # raised a bare AssertionError here, this is the one deliberate change
    # of exception type.
    with pytest.raises(FileNotFoundError, match=r'statement\.sta'):
        _ = mt940.parse(pathlib.Path('/nonexistent/statement.sta'))


class _StatementWithRead(str):  # noqa: FURB189 (a str subclass is the point)
    """A str that also has a read() method, which 5.0.0 read through."""

    __slots__: typing.ClassVar[tuple[str, ...]] = ()

    def read(self) -> str:
        return self.replace('REF', 'FROM-READ')


def test_anything_with_a_read_method_is_read_first() -> None:
    # 5.0.0 checked for read() before anything else, so even a str
    # subclass is treated as a handle.
    transactions = mt940.parse(_StatementWithRead(_BOM_STATEMENT))
    assert transactions.data['transaction_reference'] == 'FROM-READ'


def test_file_descriptor_is_read_and_closed() -> None:
    # 5.0.0 accepted an int through os.path.isfile and open(), which closes
    # the descriptor on the way out.
    fd = os.open(_ING, os.O_RDONLY)
    try:
        transactions = mt940.parse(fd)
        with pytest.raises(OSError, match='Bad file descriptor'):
            _ = os.fstat(fd)
    finally:
        # parse() closed the descriptor, this only matters when the
        # assertion above fails.
        with contextlib.suppress(OSError):
            os.close(fd)
    assert len(transactions) == len(mt940.parse(_ING))


@pytest.mark.parametrize(
    'source',
    [None, [':20:REF'], bytearray(b':20:REF'), memoryview(b':20:REF')],
    ids=['none', 'list', 'bytearray', 'memoryview'],
)
def test_unsupported_sources_raise_type_error(source: object) -> None:
    # 5.0.0 raised TypeError out of os.stat for these.
    with pytest.raises(TypeError, match='unsupported source type'):
        _ = mt940.parse(typing.cast('mt940._types.Source', source))


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


def test_unpickle_state_from_before_options_and_boundary() -> None:
    # Pickles written by 4.x carry neither `transaction_boundary` (5.0.0)
    # nor `options` (5.1.0). Both are backfilled so the restored object can
    # parse again instead of raising AttributeError.
    with _ING.open(encoding='utf-8') as fh:
        transactions = mt940.parse(fh.read())
    # A real round trip (of our own, trusted pickle) gives an independent
    # copy of the state. Dropping the two newer attributes from it mimics a
    # pickle written by 4.x.
    state = pickle.loads(pickle.dumps(transactions)).__getstate__()
    del state['options'], state['transaction_boundary']
    restored = mt940.models.Transactions.__new__(mt940.models.Transactions)
    restored.__setstate__(state)

    assert restored.options == mt940.Options()
    assert restored.transaction_boundary == frozenset()
    assert len(restored.parse(_BOM_STATEMENT)) == len(transactions) + 1


class _Legacy500Transactions(mt940.models.Transactions):
    """A subclass with the 5.0.0 constructor, which predates `options`."""

    def __init__(
        self,
        processors: mt940._types.Processors | None = None,
        tags: dict[int | str, mt940.tags.Tag] | None = None,
        transaction_boundary: Iterable[str] | None = None,
    ) -> None:
        super().__init__(processors, tags, transaction_boundary)


def test_parse_builds_a_subclass_with_the_5_0_0_constructor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Code written against 5.0.0 may install a Transactions subclass whose
    # constructor does not take `options`. Without options to pass on, the
    # parser must not pass the keyword at all.
    monkeypatch.setattr(mt940.models, 'Transactions', _Legacy500Transactions)

    parsed = mt940.parse(_BOM_STATEMENT)
    assert isinstance(parsed, _Legacy500Transactions)
    assert len(parsed) == 1

    statements = mt940.parse_statements(_BOM_STATEMENT + _BOM_STATEMENT)
    assert [len(statement) for statement in statements] == [1, 1]
    assert all(isinstance(s, _Legacy500Transactions) for s in statements)


_TWO_86_STATEMENT = """:20:REF
:25:NL
:28C:1/1
:60F:C091019EUR1000,00
:61:0910201020C500,00NTRFCUSTREF//BANKREF
:86:166?00SEPA?20SVWZ+one
:86:166?00SEPA?20KREF+K2?21SVWZ+two
:62F:C091020EUR1500,00
"""


def test_structured_86_none_overwrites_by_default() -> None:
    # 5.0.0 semantics: the first structured :86: carries no KREF, so its
    # customer_reference of None replaces the one from :61:. The second
    # :86: then replaces that None with its KREF. (5.0.0 itself crashed on
    # the second tag with None += str, that part is a plain fix.)
    transaction = mt940.parse(_TWO_86_STATEMENT)[0].data
    assert transaction['customer_reference'] == 'K2'
    assert transaction['purpose'] == 'one\ntwo'


def test_merge_keeps_values_option_preserves_existing_values() -> None:
    # With the option a None never replaces a value another tag provided,
    # so the :61: reference survives and the KREF is appended to it.
    options = mt940.Options(merge_keeps_values=True)
    transaction = mt940.parse(_TWO_86_STATEMENT, options=options)[0].data
    assert transaction['customer_reference'] == 'CUSTREF\nK2'
    assert transaction['purpose'] == 'one\ntwo'


def test_merge_keeps_values_option_still_fills_missing_keys() -> None:
    # A key that no earlier tag provided is set even when its value is
    # None, in both modes.
    statement = _TWO_86_STATEMENT.replace('KREF+K2?21', '')
    for options in (mt940.Options(), mt940.Options(merge_keeps_values=True)):
        transaction = mt940.parse(statement, options=options)[0].data
        assert 'applicant_creditor_id' in transaction
        assert transaction['applicant_creditor_id'] is None
