import collections
from mt940 import processors

def test_process_segments_29_bic_removed():
    # Create a pseudo OrderedDict similar to what _parse_segments returns.
    tmp = collections.OrderedDict()
    # Segment with key "29" ending with " BIC" should have the trailing " BIC" removed.
    tmp["29"] = "DE69280123450012345670 BIC"
    result = processors._process_segments(tmp)
    key20 = processors.DETAIL_KEYS["20"]
    # After removal, expect "DE69280123450012345670" to be appended.
    assert key20 in result
    assert result[key20] == ["DE69280123450012345670"]

def test_process_segments_other_fields():
    # Test normal behavior for other segments.
    tmp = collections.OrderedDict()
    # Field "20" is present in DETAIL_KEYS so goes to its own key.
    tmp["20"] = "Purpose Text"
    # Field "29" that does not end with " BIC" should remain unchanged.
    tmp["29"] = "Another Example"
    result = processors._process_segments(tmp)
    key20 = processors.DETAIL_KEYS["20"]
    # Both values should be appended to the same key.
    assert key20 in result
    assert result[key20] == ["Purpose Text", "Another Example"]
