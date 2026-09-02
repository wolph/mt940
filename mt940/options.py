"""Opt-in parser behaviours.

Every attribute of :class:`Options` defaults to what release 5.0.0 does, so
upgrading never changes parsed output on its own. Each attribute switches on
one fix that changes the output for input 5.0.0 parsed without complaint.
Pass an instance to :func:`mt940.parse`, :func:`mt940.parse_statements` or
:class:`mt940.models.Transactions`, or use :meth:`Options.all` to opt in to
every fix at once. The next major release enables all of them by default.

Example:
    >>> import mt940
    >>> options = mt940.Options(reversal_sign=True, applicant_iban=True)
    >>> options.reversal_sign, options.strip_bom
    (True, False)
    >>> mt940.Options.all().strip_bom
    True
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class Options:
    """Switches for behaviour that differs from release 5.0.0.

    Every switch is off by default, so parsing without options gives the
    5.0.0 output. The next major release switches all of them on.
    """

    #: File the ``?31`` sub-field of a structured ``:86:`` under
    #: ``applicant_iban`` instead of prepending it to ``applicant_name``
    #: (issue #132, the 4.x behaviour).
    applicant_iban: bool = False

    #: A structured ``:86:`` emits ``None`` for every sub-field it does not
    #: carry. With this on, such a ``None`` never replaces a value another
    #: tag already provided, so the ``:61:`` customer reference survives an
    #: ``:86:`` without a ``KREF``.
    merge_keeps_values: bool = False

    #: Give the ``:61:`` reversal-of-credit mark ``RC`` a negative amount,
    #: like the debit it is (issue #130).
    reversal_sign: bool = False

    #: Treat lowercase debit/credit marks (``d``, ``c``, ``rc``, ``rd``) like
    #: their uppercase forms when signing an amount. The tag patterns already
    #: accept them.
    case_insensitive_marks: bool = False

    #: Read the ``:13D:`` offset as hours and minutes, so ``+0100`` is one
    #: hour. 5.0.0 read the digits as a minute count.
    timezone_offset: bool = False

    #: Keep ``:86:`` details of any length. 5.0.0 silently truncated them
    #: after nine chunks of 65 characters.
    unbounded_details: bool = False

    #: Keep the content of ``:NS:`` lines that do not start with a two-digit
    #: sub-tag. 5.0.0 replaced such a line with an empty one when it followed
    #: a sub-tag line.
    non_swift_free_text: bool = False

    #: Treat a blank ``:34F:`` debit/credit mark as "both", giving
    #: ``d_floor_limit`` and ``c_floor_limit`` and a statement currency.
    #: 5.0.0 produced a key with a leading space.
    floor_limit_blank_mark: bool = False

    #: Drop a leading byte-order mark, so the first ``:20:`` tag is
    #: recognised. 5.0.0 kept it and lost that tag.
    strip_bom: bool = False

    #: Keep free text in front of the first GVC keyword of a ``?20`` purpose
    #: when it contains a ``+`` in its first four characters. 5.0.0 dropped
    #: that text.
    gvc_leading_text: bool = False

    @classmethod
    def all(cls) -> Options:
        """Return an instance with every fix switched on.

        Returns:
            The options the next major release will use by default.
        """
        return cls(**dict.fromkeys(cls.names(), True))

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return the attribute names, in declaration order.

        Returns:
            The option names.
        """
        return tuple(field.name for field in dataclasses.fields(cls))
