##################################################
# MIT License
#
# Copyright (c) 2019 Learning Equality
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
##################################################

import re
from googleclient import GoogleDriveClient, StandardEntry, StandardEntryList
from kicd.validation import *


def extract_bullets(items, patterns=[r"\d+\.\d+\.\d+", r"[a-zA-Z0-9]{1,3}\)"]):
    for item in items:
        assert not item.bullet, "item already has bullet: {}".format(item)
        for pattern in patterns:
            match = re.findall("^" + pattern, item.text)
            if match:
                item.bullet = match[0].strip()
                item.text = item.text[len(item.bullet) :].strip()
                break


def parse_doc_to_line_items(file_id="1p48DXwSDtKzZVcW5UHnRpRwn4jQq5Abv-4jcJtQf9lk"):

    client = GoogleDriveClient()
    doc = client.get_doc(file_id)
    html = doc.read().decode()
    items = client.extract_line_items_from_html(html)

    extract_bullets(items)

    assert_top_level_numbers_are_sequential_and_properly_indented(items)
    assert_all_top_level_bullets_are_dotted_numbers(items)
    assert_parenthetical_bullets_are_sequential(items)
    assert_standard_numbering_titles(items)
    assert_all_section_headers_have_lesson_count(items)

    return items


def extract_topic_notes(items, start_index):
    assert items[start_index].bullet.endswith(".0.0")
    i = start_index + 1
    notes = ""
    started = False
    first_index = None
    last_index = None
    while (
        i < len(items) and items[i].indent > 0 and not items[i].bullet.endswith(".0.0")
    ):
        item = items[i]
        titletext = item.text.title()
        if titletext.startswith("Suggested") or titletext.startswith("Note"):
            if not started:
                first_index = i
            started = True
            i += 1
            continue
        if started:
            notes += "- {}{}\n".format(item.get_bullet_with_space(), item.text)
        last_index = i
        i += 1
    linespan = range(first_index, last_index + 1) if first_index and last_index else []
    return linespan, notes.strip()


def extract_objectives(items, start_index):
    assert items[start_index].bullet.endswith(".1.0")
    objectives = []
    first_index = start_index + 1
    last_index = None
    i = start_index + 2  # jump into objectives list
    while i < len(items) and not items[i].bullet.endswith(".2.0"):
        item = items[i]
        if item.indent == 3:  # learning objective
            assert ")" in item.bullet, "Objective bullet format incorrect: {}".format(
                item.text
            )
            objectives.append(
                StandardEntry(
                    level=4,
                    item_type="learning_objective",
                    text=item.text,
                    identifier=item.bullet,
                )
            )
        elif item.indent > 3:  # notes under learning objective
            objectives[-1].add_note_line(
                item.get_bullet_with_space() + item.text, indent=item.indent - 4
            )
        else:
            raise Exception(
                "Bad indentation on items under:\n{}".format(str(items[start_index]))
            )

        last_index = i
        i += 1
    linespan = range(first_index, last_index + 1) if first_index and last_index else []
    return linespan, objectives


def add_descendant_items_to_notes(items, start_index, entry, lines_to_skip):
    base_indent = items[start_index].indent
    first_index = start_index + 1
    last_index = None

    i = first_index
    while i < len(items) and items[i].indent > base_indent:
        if i in lines_to_skip:
            i += 1
            continue
        item = items[i]
        entry.add_note_line(
            item.get_bullet_with_space() + item.text,
            indent=item.indent - base_indent - 1,
        )
        last_index = i
        i += 1

    linespan = range(first_index, last_index + 1) if first_index and last_index else []

    return linespan


def extract_standard_entries_from_line_items(items):
    entries = []
    lines_to_skip = set([])
    for index, item in enumerate(items):
        if index in lines_to_skip:
            continue
        if item.indent == 0:  # form or subject area
            if item.text.lower().startswith("form"):
                entries.append(
                    StandardEntry(level=2, item_type="level", text=item.text)
                )
            else:
                entries.append(
                    StandardEntry(level=1, item_type="subject", text=item.text)
                )
        elif item.indent == 1:  # topic or sections under topic

            # extract the item numbers from the dot notation
            number = re.search(r"(\d+)\.(\d+)\.(\d+)", item.bullet)
            unit, section, subsection = (
                int(number.group(1)),
                int(number.group(2)),
                int(number.group(3)),
            )

            if section == 0 and subsection == 0:  # topic

                # find any notes attached
                linespan, notes = extract_topic_notes(items, index)
                lines_to_skip.update(linespan)

                # extract and remove the lesson count
                topicmatches = re.search(
                    r"^(.*) \((\d+) Lessons?\)", item.text, flags=re.IGNORECASE
                )
                if topicmatches:
                    text, units = topicmatches.group(1), topicmatches.group(2)
                else:
                    units = ""

                entries.append(
                    StandardEntry(
                        level=3,
                        item_type="topic",
                        text=text,
                        units=units,
                        notes=notes,
                        identifier=item.bullet,
                    )
                )

            if section == 1:  # learning objective section

                linespan, objectives = extract_objectives(items, index)
                lines_to_skip.update(linespan)
                entries += objectives

            if section in [2, 3] and subsection > 0:  # content or project items

                if section == 2:
                    item_type = "content"
                elif section == 3:
                    item_type = "project"

                entry = StandardEntry(
                    level=4, item_type=item_type, text=item.text, identifier=item.bullet
                )

                linespan = add_descendant_items_to_notes(
                    items, index, entry, lines_to_skip
                )
                lines_to_skip.update(linespan)

                entries.append(entry)

    return StandardEntryList(entries)
