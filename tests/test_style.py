from demo import style

SOURCE = (
    "The Caterpillar 966H is a versatile midsize wheel loader engineered for quarrying and "
    "mining. Powered by an 11.1 L Cat C11 ACERT diesel engine, it delivers up to 286 hp."
)

# Written the way the desk writes: news first, long and short sentences mixed.
HUMAN = (
    "Caterpillar built the 966H for quarry and mine work, and fitted it with an 11.1 L Cat "
    "C11 ACERT diesel that makes up to 286 hp. Production ran from 2006. The loader weighs "
    "23,125 kg."
)


def test_decimals_and_units_do_not_split_a_sentence():
    assert style.sentences("It has an 11.1 L engine and holds 4.8 m³. It weighs 23,125 kg.") == [
        "It has an 11.1 L engine and holds 4.8 m³.",
        "It weighs 23,125 kg.",
    ]


def test_desk_style_writing_has_no_problems():
    assert style.problems(HUMAN, SOURCE, "en") == []


def test_opening_on_a_product_description_is_a_problem():
    text = "The Caterpillar 966H is a midsize wheel loader. " + HUMAN
    assert any("The Caterpillar 966H is" in p for p in style.problems(text, SOURCE, "en"))


def test_two_sentences_in_a_row_opening_alike_is_a_problem():
    text = (
        "It uses an 11.1 L Cat C11 ACERT diesel engine that makes up to 286 hp in quarry work. "
        "It weighs 23,125 kg."
    )
    assert any("open" in p for p in style.problems(text, SOURCE, "en"))


def test_an_ing_add_on_at_the_end_of_a_sentence_is_a_problem():
    text = HUMAN.replace("makes up to 286 hp.", "makes up to 286 hp, making it a strong choice.")
    assert any("making" in p for p in style.problems(text, SOURCE, "en"))


def test_a_sales_word_the_source_never_used_is_a_problem():
    text = HUMAN.replace("fitted it with", "equipped it, featuring")
    assert any("featuring" in p for p in style.problems(text, SOURCE, "en"))


def test_a_word_the_source_itself_uses_is_not_a_problem():
    text = HUMAN.replace("for quarry and mine work", "as a versatile loader for quarries")
    assert not any("versatile" in p for p in style.problems(text, SOURCE, "en"))


def test_sentences_all_the_same_length_are_a_problem():
    even = (
        "Caterpillar built the 966H loader for quarries and mines. "
        "An 11.1 L Cat C11 ACERT diesel makes up to 286 hp. "
        "Factory production of the loader ended in 2012."
    )
    assert any("length" in p for p in style.problems(even, SOURCE, "en"))


def test_a_closing_sentence_that_sums_up_is_a_problem():
    text = HUMAN + " Overall, the loader suits heavy work."
    assert any("Overall" in p for p in style.problems(text, SOURCE, "en"))


def test_french_and_arabic_are_checked_only_for_their_own_tell_words():
    french = "Caterpillar a construit la 966H. Par ailleurs, elle pèse 23 125 kg."
    assert style.problems(french, "", "fr") == ['"par ailleurs"']
    assert style.problems("صنعت كاتربيلر الرافعة 966H.", "", "ar") == []


def test_the_rules_are_written_for_the_prompt():
    assert "10 words longer" in style.RULES
    assert "making it" in style.RULES
