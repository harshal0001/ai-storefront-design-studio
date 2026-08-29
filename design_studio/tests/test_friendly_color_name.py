from conversational_agent.color_engine import friendly_color_name


def test_friendly_color_name_avoids_hex_in_label():
    assert "#" not in friendly_color_name("#1E5F8C")
    assert "ocean" in friendly_color_name("#1E5F8C").lower()
    assert friendly_color_name("#F8F4EF").startswith("Pale ")
    assert friendly_color_name("#BE185D") == "Berry"
