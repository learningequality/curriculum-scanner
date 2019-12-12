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

from scanner import CurriculumScanner
from classes import *
from extraction_utils import *


def extract_markdown_from_document(doc, start_page=0, end_page=None):

    if not end_page:
        end_page = len(doc.pages) - 1

    all_items = ItemList([])

    for page_num in range(start_page, end_page + 1):
        img = PageImage(doc.get_page_image(page_num))
        page_data = doc.get_page_data(page_num)

        bullets = get_bullets_by_template(img)

        # extract the columns
        columns = determine_column_bounding_boxes(
            page_data,
            plot_density=False,
            smoothing_granularity=8,
            prominence=1,
            width=50,
        )

        # extract the items by column, and add onto our list
        for column_box in columns:
            items = extract_single_line_items_from_column(
                page_data, column_box=column_box, bullets=bullets
            )
            all_items += items

    # go through and combine items together that belong together
    all_items = all_items.combine_lines()

    # annotate the lines with an estimate of their font weight
    annotate_lines_with_font_weight(all_items, img)

    annotate_items_with_tab_levels_for_kicd(
        all_items,
        same_level_threshold=0.025,
        same_fontweight_threshold=0.25,
        print_debug_info=False,
    )

    return all_items


def render_to_markdown(items):
    text = ""
    for item in items:
        text += "\t" * item.tabs + "- "
        if item.bullet and item.bullet.text not in ["-", "•"]:
            text += item.bullet.text + " "
        text += item.get_text() + "\n"
    return text
