from app.wdiff import PARA, diff_units, tokenize


def test_tokenize_keeps_punctuation_separate():
    tokens = [t.text for t in tokenize("striking out the figure “20”, and inserting")]
    assert "20" in tokens
    assert "," in tokens


def test_tokenize_marks_paragraph_breaks():
    tokens = [t.text for t in tokenize("para one\n\npara two")]
    assert PARA in tokens


def test_identical_text_has_no_marks():
    d = diff_units("the same text here.", "the same   text here.")
    assert d.identical
    assert not any(changed for _, changed in d.left_marked)


def test_word_level_difference_marked_on_both_sides():
    d = diff_units("a speed limit of 20 miles per hour",
                   "a speed limit of 25 miles per hour")
    assert not d.identical
    left_changed = [t.text for t, c in d.left_marked if c]
    right_changed = [t.text for t, c in d.right_marked if c]
    assert left_changed == ["20"]
    assert right_changed == ["25"]


def test_punctuation_only_difference_detected():
    d = diff_units("cities and towns;", "cities and towns:")
    assert not d.identical
    assert [t.text for t, c in d.left_marked if c] == [";"]
