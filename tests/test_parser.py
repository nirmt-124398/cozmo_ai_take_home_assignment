from __future__ import annotations

from cozmo_ai_take_home.parsing import parse_segment


def test_quantity_prefix_and_suffix() -> None:
    prefix = parse_segment("2 laptops")
    suffix = parse_segment("laptop x2")

    assert (prefix.qty, prefix.item_text) == (2, "laptops")
    assert (suffix.qty, suffix.item_text) == (2, "laptop")


def test_size_attribute_and_raw_text_are_preserved() -> None:
    observation = parse_segment("55 inch tv")

    assert observation.raw_text == "55 inch tv"
    assert observation.qty == 1
    assert observation.item_text == "tv"
    assert observation.attributes == {"size_inch": 55}
