def test_hundreds_multiply_a_following_thousand() -> None:
    from ulauncher.modes.launcher.number_words import replace_number_words

    # "two hundred" becomes "200" first, and the bare thousand rule then left "200 1000"
    assert replace_number_words("two hundred thousand") == "200000"
    assert replace_number_words("a hundred thousand") == "100000"
    assert replace_number_words("two thousand") == "2000"
    assert replace_number_words("twenty thousand") == "20000"
    assert replace_number_words("five hundred million") == "500000000"
    assert replace_number_words("thousand") == "1000"
