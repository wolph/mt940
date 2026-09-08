Read files, text and streams
============================

Choose an input form that makes your application's intent explicit.
:func:`mt940.parse` and :func:`mt940.parse_statements` use the same source
reader and accept the following forms.

.. list-table:: Source dispatch
   :header-rows: 1
   :widths: 25 45 30

   * - Source
     - Interpretation
     - Ownership and failure
   * - ``str`` or ``bytes``
     - An existing regular filename is read. Otherwise the value is inline
       statement content.
     - A misspelled string filename can parse as empty text.
   * - :class:`pathlib.Path` or another path-like object
     - Always a filename.
     - Missing or non-regular paths raise ``FileNotFoundError``.
   * - Open text stream
     - ``read()`` returns remaining text.
     - Current position is used. The stream stays open.
   * - Open binary stream
     - ``read()`` returns remaining bytes, then decoding runs.
     - Current position is used. The stream stays open.
   * - Integer file descriptor
     - Wrapped in a binary file object and read.
     - The descriptor closes after reading. Duplicate it first if ownership
       must remain with the caller.

The reader tests for a ``read`` attribute before the other forms. A custom
reader's exceptions propagate. The structural check does not validate its
signature or return type in advance. :data:`mt940._types.Source` describes the
annotated public input union, and :func:`mt940.parser._load` documents dispatch.

Text, bytes and in-memory streams
---------------------------------

These sources all contain the same synthetic reference:

.. doctest::

   >>> import io
   >>> import mt940
   >>> source: str = ':20:EXAMPLE'
   >>> mt940.parse(source).data['transaction_reference']
   'EXAMPLE'
   >>> mt940.parse(source.encode('utf-8')).data['transaction_reference']
   'EXAMPLE'
   >>> stream: io.StringIO = io.StringIO(source)
   >>> mt940.parse(stream).data['transaction_reference']
   'EXAMPLE'
   >>> stream.closed
   False
   >>> mt940.parse(stream).data
   {}
   >>> _ = stream.seek(0)
   >>> mt940.parse(stream).data['transaction_reference']
   'EXAMPLE'

The second stream parse has nothing left to read. Seeking back to zero makes
the source available again. The parser does not rewind caller-owned streams.

Files and descriptors
---------------------

This runnable example creates its own temporary file and transfers a duplicate
descriptor to the parser:

.. doctest::

   >>> import os
   >>> import tempfile
   >>> from pathlib import Path
   >>> with tempfile.TemporaryDirectory() as directory:
   ...     path: Path = Path(directory) / 'example.sta'
   ...     _ = path.write_text(':20:FROM-FILE', encoding='utf-8')
   ...     print(mt940.parse(path).data['transaction_reference'])
   ...     with path.open('rb') as handle:
   ...         print(mt940.parse(os.dup(handle.fileno())).data['transaction_reference'])
   ...         print(handle.closed)
   FROM-FILE
   FROM-FILE
   False

Duplicating preserves the original descriptor's ownership, but duplicate
descriptors share the underlying file position. This matters when the original
handle will be read again. See :func:`os.dup`.

Byte decoding
-------------

For bytes, ``encoding`` is the first decoder attempted. A
``UnicodeDecodeError`` falls back to UTF-8, then CP852. If no encoding is given,
UTF-8 is tried first. CP852 maps every byte, so a successful parse does not
establish that the text used the correct encoding. An unknown encoding name
raises ``LookupError`` instead of falling back. Text sources ignore
``encoding`` because they are already decoded.

When the bank specifies an encoding and incorrect bytes must be rejected,
decode explicitly before parsing:

.. doctest::

   >>> raw: bytes = ':20:ENCODING\n:25:Example'.encode('utf-8')
   >>> decoded: str = raw.decode('utf-8', errors='strict')
   >>> mt940.parse(decoded).data['account_identification']
   'Example'

To recognise ``:20:`` after a leading byte-order mark, pass
``options=mt940.Options(strip_bom=True)``. The high-level reader removes one
leading U+FEFF after decoding. Direct
:meth:`mt940.models.Transactions.parse` accepts decoded text and does not apply
that switch. :doc:`compatibility` covers the other switches.
