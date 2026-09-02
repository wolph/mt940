import pathlib
import pickle

import mt940
import pytest

_tests_path = pathlib.Path(__file__).parent


@pytest.mark.parametrize(
    ('path', 'encoding'),
    [
        (_tests_path / 'jejik' / 'ing.sta', 'utf-8'),
        (_tests_path / 'self-provided' / 'raphaelm.sta', 'utf-8'),
        (_tests_path / 'betterplace' / 'with_binary_character.sta', 'utf-8'),
    ],
)
def test_non_ascii_parse(path, encoding) -> None:
    # Read as binary
    with path.open('rb') as fh:
        data = fh.read()
        data = data.decode(encoding)
        pickle.dumps(mt940.parse(data))

    # Read as text
    with path.open('r') as fh:
        data = fh.read()
        pickle.dumps(mt940.parse(data))


_BOM_STATEMENT = (
    ':20:REF\n'
    ':25:NL00BANK0123456789\n'
    ':28C:1/1\n'
    ':60F:C091019EUR1000,00\n'
    ':61:0910201020C500,00NTRFNONREF//B\n'
    ':86:Example transaction\n'
    ':62F:C091020EUR1500,00\n'
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


def test_86_line_with_embedded_tag_lookalike_stays_in_details() -> None:
    # A :86: free-text line that itself starts with a tag-lookalike (:12:,
    # which is not a known tag) must not be split off as a separate tag and
    # corrupt the statement -- it stays part of the transaction details.
    transactions = mt940.parse(
        ':20:R\n:25:A\n:28C:1\n:60F:C240101EUR0,00\n'
        ':61:2401010101C10,00NTRFREF//B\n'
        ':86:PAYMENT FOR\n:12:INVOICE STYLE REF\n'
        ':62F:C240101EUR10,00\n'
    )
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
    data = (
        '{1:F01BANKNL2AXXXX0000000000}{2:I940BANKNL2AXXXXN}{4:\n'
        ':20:STMT1\n:25:NL00BANK1\n:28C:1/1\n:60F:C240101EUR100,00\n'
        ':62F:C240101EUR100,00\n-}\n'
        ':20:STMT2\n:25:NL00BANK2\n:28C:2/1\n:60F:C240102EUR200,00\n'
        ':62F:C240102EUR200,00\n-\n'
    )
    statements = mt940.parse_statements(data)
    assert [s.data['transaction_reference'] for s in statements] == [
        'STMT1',
        'STMT2',
    ]


def test_86_continuation_preserves_leading_whitespace() -> None:
    # Transactions.strip only rstrips, so significant leading whitespace on a
    # :86: continuation line is preserved rather than eaten.
    transactions = mt940.parse(
        ':20:R\n:25:A\n:28C:1\n:60F:C240101EUR0,00\n'
        ':61:2401010101C10,00NTRFREF//B\n'
        ':86:LINE ONE\n    INDENTED TWO\n'
        ':62F:C240101EUR10,00\n'
    )
    assert transactions[0].data['transaction_details'] == (
        'LINE ONE\n    INDENTED TWO'
    )


def test_pickle_roundtrip_restores_processors() -> None:
    # __getstate__ drops the (unpicklable) processors; __setstate__ must
    # restore them so the unpickled object is still usable.
    with (_tests_path / 'jejik' / 'ing.sta').open() as fh:
        transactions = mt940.parse(fh.read())

    # Trusted, self-produced pickle (a round-trip of our own object), so
    # pickle.loads is safe here.
    restored = pickle.loads(pickle.dumps(transactions))

    assert restored.processors == transactions.processors
    assert len(restored) == len(transactions)
    # Re-parsing exercises the restored processors without raising.
    restored.parse('')


def test_pickle_roundtrip_preserves_transaction_boundary() -> None:
    # __getstate__ only drops `processors`; newer state such as the opt-in
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
