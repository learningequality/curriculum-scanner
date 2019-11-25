import re


def assert_top_level_numbers_are_sequential_and_properly_indented(
    items, exceptions=["32.2.4", "44.2.3"]
):
    last_unit, last_section, last_subsection = None, None, None
    for item in items:
        header = re.search(r"(\d+)\.(\d+)\.(\d+)", item.bullet or "")
        if not header:
            continue
        if item.indent != 1:
            print(
                "Expected indentation of 1, got {}, in line:\n{}\n\n".format(
                    item.indent, str(item)
                )
            )
            continue
        unit, section, subsection = (
            int(header.group(1)),
            int(header.group(2)),
            int(header.group(3)),
        )
        if last_unit is not None and item.bullet not in exceptions:
            if unit == last_unit:
                if section == last_section:
                    if subsection != last_subsection + 1:
                        print(
                            "Expected {}, got {}, in line:\n{}\n\n".format(
                                "{}.{}.{}".format(unit, section, last_subsection + 1),
                                item.bullet,
                                str(item),
                            )
                        )
                else:
                    if section != last_section + 1 or subsection != 0:
                        print(
                            "Expected {}, got {}, in line:\n{}\n\n".format(
                                "{}.{}.{}".format(unit, last_section + 1, 0),
                                item.bullet,
                                str(item),
                            )
                        )
            else:
                if (
                    (unit != 1 and unit != last_unit + 1)
                    or section != 0
                    or subsection != 0
                ):
                    print(
                        "Expected {}, got {}, in line:\n{}\n\n".format(
                            "{}.{}.{}".format(last_unit + 1, 0, 0),
                            item.bullet,
                            str(item),
                        )
                    )

        last_unit, last_section, last_subsection = unit, section, subsection


def assert_all_section_headers_have_lesson_count(items, exceptions=["3.0.0", "53.0.0"]):
    for i, item in enumerate(items):
        if item.indent != 1:
            continue
        if not item.bullet.endswith(".0.0"):
            continue
        if item.bullet in exceptions:
            continue
        if not re.search(r"^(.*) \((\d+) Lessons?\)", item.text, flags=re.IGNORECASE):
            print(
                "Expected 'A.B.C ______ (X Lessons)', got:\n{}\n{}\n{}\n\n".format(
                    *items[i - 1 : i + 2]
                )
            )


def assert_all_top_level_bullets_are_dotted_numbers(items):
    for i, item in enumerate(items):
        if item.indent != 1:
            continue
        header = re.search(r"(\d+)\.(\d+)\.(\d+)", item.bullet or "")
        if not header:
            print(
                "Should not be at top-level of bullets:\n{}\n{}\n{}\n\n".format(
                    *items[i - 1 : i + 2]
                )
            )


def assert_parenthetical_bullets_are_sequential(items):

    roman_numerals = [
        "i",
        "ii",
        "iii",
        "iv",
        "v",
        "vi",
        "vii",
        "viii",
        "ix",
        "x",
        "xi",
        "xii",
        "xiii",
        "xiv",
        "xv",
        "xvi",
        "xvii",
        "xviii",
        "xix",
        "xx",
    ]

    last_bullet_by_level = []

    for i, item in enumerate(items):

        level = item.indent

        while len(last_bullet_by_level) < level:
            last_bullet_by_level.append(None)

        while len(last_bullet_by_level) > level:
            last_bullet_by_level.pop()

        if not item.bullet or ")" not in item.bullet:
            last_bullet = None
            last_level = None
            continue

        last_bullet = last_bullet_by_level[-1]
        bullet = item.bullet.strip(")")

        if not last_bullet:
            expected = ["a", "i"]
        elif last_bullet == "i":
            expected = ["j", "ii"]
        elif last_bullet in roman_numerals:
            expected = [roman_numerals[roman_numerals.index(last_bullet) + 1]]
        elif len(bullet) > 1:
            print(
                "We expected a single-character bullet but got '{}':\n{}\n{}\n{}\n\n".format(
                    bullet, *items[i - 1 : i + 2]
                )
            )
        else:
            expected = [chr(ord(last_bullet) + 1)]

        if bullet not in expected:
            print(
                "We expected a bullet from {} but got '{}':\n{}\n{}\n{}\n\n".format(
                    expected, bullet, *items[i - 1 : i + 2]
                )
            )

        last_bullet_by_level[-1] = bullet


def assert_standard_numbering_titles(items):
    for i, item in enumerate(items):
        header = re.search(r"(\d+)\.(\d+)\.(\d+)", item.bullet or "")
        if not header:
            continue
        unit, section, subsection = (
            int(header.group(1)),
            int(header.group(2)),
            int(header.group(3)),
        )
        if section == 1 and subsection == 0:
            options = ["Specific Objectives", "Specific Objective"]
            if item.text.title() not in options:
                print(
                    "Title for {} should be one of {}:\n{}\n{}\n{}\n\n".format(
                        item.bullet, options, *items[i - 1 : i + 2]
                    )
                )
            next_item = items[i + 1]
            next_item_text = next_item.text.strip(":").lower()
            if not next_item_text.startswith(
                "by the end of th"
            ) or not next_item_text.endswith("the learner should be able to"):
                print(
                    "Title for {} should be 'By the end of (this|the) topic, the learner should be able to:':\n{}\n{}\n{}\n\n".format(
                        item.bullet, *items[i : i + 3]
                    )
                )
        if section == 2 and subsection == 0:
            options = ["Contents", "Content"]
            if item.text.title() not in options:
                print(
                    "Title for {} should be one of {}:\n{}\n{}\n{}\n\n".format(
                        item.bullet, options, *items[i - 1 : i + 2]
                    )
                )
        if section == 3 and subsection == 0:
            options = [
                "Project Work",
                "Projects",
                "Project",
                "Practical Activities",
                "Excursion",
            ]
            if item.text.title() not in options:
                print(
                    "Title for {} should be one of {}:\n{}\n{}\n{}\n\n".format(
                        item.bullet, options, *items[i - 1 : i + 2]
                    )
                )
