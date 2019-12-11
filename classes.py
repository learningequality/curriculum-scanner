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

from config import BULLET_THRESHOLD
from functools import reduce
from PIL import Image, ImageDraw
import cv2
import numpy as np
import re


class BoundingBox(object):
    def __init__(self, x1, y1, x2, y2):
        if x1 >= x2:
            print(x1, y1, x2, y2)
        assert x1 < x2
        assert y1 < y2
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def center(self):
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    def area(self):
        return self.width() * self.height()

    def width(self):
        return self.x2 - self.x1

    def height(self):
        return self.y2 - self.y1

    def expanded(self, factor, axis="both"):
        assert axis in ["both", "x", "y"], "`axis` must be one of 'both', 'x', or 'y'"
        x1, y1, x2, y2 = self.x1, self.y1, self.x2, self.y2
        if axis in ["x", "both"]:
            width = self.width()
            x1 -= factor * width
            x2 += factor * width
        elif axis in ["y", "both"]:
            height = self.height()
            y1 -= factor * height
            y2 += factor * height
        return BoundingBox(int(x1), int(y1), int(x2), int(y2))

    def shrunk(self, factor, axis="both"):
        return self.expanded(-factor, axis=axis)

    def shifted(self, x, y):
        return BoundingBox(self.x1 + x, self.y1 + y, self.x2 + x, self.y2 + y)

    def __and__(self, other):
        # returns the intersection of the bounding boxes
        x1 = max(self.x1, other.x1)
        y1 = max(self.y1, other.y1)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        if (x2 <= x1) or (y2 <= y1):
            return None
        return BoundingBox(x1, y1, x2, y2)

    def __or__(self, other):
        # returns the union of the bounding boxes (box that contains both)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        x2 = max(self.x2, other.x2)
        y2 = max(self.y2, other.y2)
        return BoundingBox(x1, y1, x2, y2)

    def overlap(self, other, axis="both"):
        """
        Calculate the Intersection over Union (IoU) of two bounding boxes.
        Adapted from: https://stackoverflow.com/questions/25349178/calculating-percentage-of-bounding-box-overlap-for-image-detector-evaluation
        """
        assert axis in ["both", "x", "y"], "`axis` must be one of 'both', 'x', or 'y'"
        if axis == "x":
            self = BoundingBox(self.x1, 0, self.x2, 1)
            other = BoundingBox(other.x1, 0, other.x2, 1)
        elif axis == "y":
            self = BoundingBox(0, self.y1, 1, self.y2)
            other = BoundingBox(0, other.y1, 1, other.y2)

        intersection = self & other
        if intersection is None:
            return 0.0
        intersection_area = intersection.area()

        # compute the intersection over union by taking the intersection area and dividing it
        # by the sum of the two areas minus the intersection area
        return intersection_area / float(self.area() + other.area() - intersection_area)

    def get_subimage(self, img):
        return img[self.y1 : self.y2, self.x1 : self.x2, :].copy()

    def __contains__(self, item):
        intersection = self & item
        if intersection is None:
            return False
        return item.overlap(intersection) > 0.8

    def __str__(self):
        return "({}, {})/({}, {})".format(self.x1, self.y1, self.x2, self.y2)

    def __repr__(self):
        return "<BoundingBox: {}>".format(str(self))


class BoundingBoxSet(list):
    def __init__(self, *args, overlap_threshold=0.4, **kwargs):
        self.overlap_threshold = overlap_threshold
        super().__init__(*args, **kwargs)

    def get_outer_box(self):
        return reduce(lambda a, b: a | b, self)

    def __and__(self, other):
        # returns the bounding boxes that are in both sets (intersection)
        results = BoundingBoxSet(overlap_threshold=self.overlap_threshold)
        for box_a in self:
            for box_b in other:
                if box_a.overlap(box_b) > self.overlap_threshold:
                    results.append(box_a & box_b)
        return results

    def __or__(self, other):
        # returns the bounding boxes that are in either set (union)
        results = BoundingBoxSet(overlap_threshold=self.overlap_threshold)
        for box_a in self:
            for box_b in other:
                if box_a.overlap(box_b) > self.overlap_threshold:
                    results.append(box_a & box_b)
        return results

    def __add__(self, other):
        return self | other

    def __sub__(self, other):
        # returns the set of boxes in self but not in other
        results = BoundingBoxSet(overlap_threshold=self.overlap_threshold)
        for box_a in self:
            found = False
            for box_b in other:
                if box_a.overlap(box_b) > self.overlap_threshold:
                    found = True
                    break
            if not found:
                results.append(box_a)
        return results

    def __contains__(self, item):
        for box in self:
            if box in item and item in box:
                return True
        return False

    def deduplicate(self):
        unique = BoundingBoxSet([], overlap_threshold=self.overlap_threshold)
        for box in self:
            if box not in unique:
                unique.append(box)
        return unique


class Word(object):
    """
        Attributes:
            text: string of characters
            bounding_box: BoundingBox object with coordinates for word
    """

    bounding_box = None
    text = ""

    def __init__(self, text, bounding_box):
        self.bounding_box = bounding_box
        self.text = text

    def __repr__(self):
        return '<Word: "{}" @ {}>'.format(self.text, str(self.bounding_box))


class Line(object):
    """
        Attributes:
            words: a list of Words
            fontweight: float representing how bold the line of text is
    """

    words = None
    fontweight = None
    column_box = None

    def __init__(self, words, fontweight=None, column_box=None):
        self.fontweight = fontweight
        self.words = words or []
        self.column_box = column_box

    def add_word(self, word):
        self.words.append(word)

    def get_box(self):
        if not self.words:
            return None
        return BoundingBox(
            min(word.bounding_box.x1 for word in self.words),
            min(word.bounding_box.y1 for word in self.words),
            max(word.bounding_box.x2 for word in self.words),
            max(word.bounding_box.y2 for word in self.words),
        )

    def get_text(self):
        return " ".join([word.text for word in self.words])

    def get_indentation(self, word=None, units="col_width"):
        assert self.column_box, "line must have column_box set to calculate indentation"
        assert units in ["col_width", "pixels", "line_height"]
        if word is None:
            word = self.words[0]
        elif isinstance(word, int):
            word = self.words[word]
        indent = word.bounding_box.x1 - self.column_box.x1
        if units == "col_width":
            return indent / self.column_box.width()
        elif units == "line_height":
            return indent / np.mean([word.bounding_box.height() for word in self.words])
        elif units == "pixels":
            return indent

    def __repr__(self):
        return "<Line: {} @ {}>".format(
            [word.text for word in self.words], str(self.get_box())
        )

    def extract_bullet_by_space(self):
        # Get average character width and use that to detect wider spaces
        character_sizes = []
        for word in self.words:
            width = word.bounding_box.x2 - word.bounding_box.x1
            char_size = width / len(word.text)
            character_sizes.extend([char_size for _ in range(len(word.text))])

        threshold = np.mean(character_sizes) * BULLET_THRESHOLD
        for index, word in enumerate(self.words[:-1]):
            space = self.words[index + 1].bounding_box.x1 - word.bounding_box.x2
            if space > threshold:
                bullet_words = self.words[: index + 1]
                self.words = self.words[index + 1 :]
                return Word(
                    " ".join([w.text for w in bullet_words]),
                    BoundingBox(
                        min(word.bounding_box.x1 for word in bullet_words),
                        min(word.bounding_box.y1 for word in bullet_words),
                        max(word.bounding_box.x2 for word in bullet_words),
                        max(word.bounding_box.y2 for word in bullet_words),
                    ),
                )

    def extract_bullet_by_pattern(
        self, bullet_patterns=[r"•", r"-", r"\d+\.\d+\.\d+", r"[a-zA-Z0-9]{1,3}\)"]
    ):
        text = ""
        for index, word in enumerate(self.words):
            text += word.text.strip()
            for pattern in bullet_patterns:
                if re.match(pattern, text):
                    bullet_words = self.words[: index + 1]
                    self.words = self.words[index + 1 :]
                    return Word(
                        text.replace(" ", ""),
                        BoundingBoxSet(
                            word.bounding_box for word in bullet_words
                        ).get_outer_box(),
                    )


class Item(object):
    lines = None
    bullet = None
    tabs = None

    def __init__(self, lines, bullet=None):
        self.bullet = bullet
        self.lines = lines or []

    def set_bullet(self, bullet):
        self.bullet = bullet

    def add_lines(self, lines):
        self.lines.extend(lines)

    def get_box(self, include_bullet=False):
        boxes = [line.get_box() for line in self.lines]
        if include_bullet and self.bullet:
            boxes = [self.bullet.bounding_box] + boxes
        boxes = BoundingBoxSet([box for box in boxes if box])
        return boxes.get_outer_box()

    def get_indentation(self, include_bullet=False, units="col_width"):
        assert len(self.lines) > 0, "can't get indentation for item with no lines"
        word = self.bullet if self.bullet and include_bullet else self.lines[0].words[0]
        return self.lines[0].get_indentation(word=word, units=units)

    def average_fontweight(self):
        fontweights = [
            line.fontweight for line in self.lines if line.fontweight is not None
        ]
        if fontweights:
            return np.mean(fontweights)
        else:
            return None

    def get_text(self, separator=" "):
        text = separator.join([line.get_text().strip() for line in self.lines])
        text = (
            text.replace(" ,", ",")
            .replace(" .", ".")
            .replace(" :", ":")
            .replace(" ;", ";")
            .replace("( ", "(")
            .replace(" )", ")")
            .lstrip(".")
            .strip()
        )
        for match in re.findall(r"\d+\. \d+\. \d+", text):
            text = text.replace(match, match.replace(" ", ""))
        return text

    def __str__(self):
        text = "'{}'".format(self.get_text(separator=" "))
        if self.bullet:
            text = "[{}] {}".format(self.bullet.text, text)
        return text

    def __repr__(self):
        return "<Item: {} @ {}>".format(str(self), self.get_box())


class ItemList(list):
    def get_box(self, include_bullet=False):
        items = BoundingBoxSet(
            [item.get_box(include_bullet=include_bullet) for item in self]
        )
        return items.get_outer_box()

    def add_item(self, item):
        if item.lines:
            self.append(item)

    def combine_lines(
        self,
        header_text=[
            "Content",
            "Specific Objectives",
            "Suggested Resources",
            "Suggested Further Assessment",
            "Notes",
        ],
        factor_in_fontweight=False,
    ):
        new_items = ItemList([])
        current_item = Item([])
        prev_bold = False
        for item in self:
            # check whether there's a bullet, or the boldness of the text changed
            bold = (
                (item.lines[0].fontweight > 1)
                if factor_in_fontweight and item.lines[0].fontweight
                else False
            )
            has_bullet = bool(item.bullet)
            boldness_changed = bold != prev_bold
            if has_bullet or boldness_changed:
                new_items.add_item(current_item)
                current_item = Item([], bullet=item.bullet)
            current_item.add_lines(item.lines)
            prev_bold = bold
        new_items.add_item(current_item)

        itemlist = ItemList([item for item in new_items if item.get_text().strip()])

        # split on header text
        for i, item in list(reversed(list(enumerate(itemlist)))):
            if len(item.lines) == 1:
                continue
            found = False
            for header in header_text:
                if header in item.get_text():
                    section_starts = set([0, len(item.lines)])
                    found = ""
                    started_at = None
                    for j, line in enumerate(item.lines):
                        seeking = header[len(found) :].strip()
                        if seeking.startswith(line.get_text()):
                            if started_at is None:  # found start
                                started_at = j
                            found += " " + line.get_text()
                            if found.strip() == header:  # found end
                                section_starts.add(started_at)
                                section_starts.add(j + 1)
                                found = ""
                                started_at = None
                    section_starts = list(sorted(section_starts))
                    new_items = []
                    for ind in range(len(section_starts) - 1):
                        lines = item.lines[
                            section_starts[ind] : section_starts[ind + 1]
                        ]
                        if ind == 0:
                            new_items.append(Item(lines, bullet=item.bullet))
                        else:
                            new_items.append(Item(lines))
                    itemlist[i : i + 1] = new_items

        return itemlist


class PageImage(np.ndarray):

    _annotated_array = None

    box = None

    def __new__(
        subtype,
        source,
        dtype=float,
        buffer=None,
        offset=0,
        strides=None,
        order=None,
        box=None,
    ):
        if isinstance(source, str):
            source = cv2.imread(source)
        elif isinstance(source, Image.Image):
            source = np.array(source)

        shape = source.shape
        dtype = source.dtype
        buffer = source.copy().data

        obj = super(PageImage, subtype).__new__(
            subtype, shape, dtype, buffer, offset, strides, order
        )
        obj.box = box

        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        # Note that it is here, rather than in the __new__ method, that we set default values,
        # because this method sees all creation of default objects - with the __new__ constructor,
        # but also with arr.view(PageImage).
        self.box = getattr(obj, "box", None)

    def _initialize_annotated_array(self):
        if not self._annotated_array is not None:
            self._annotated_array = self.copy()

    def _repr_png_(self):
        self._initialize_annotated_array()
        return self.as_pil_image(annotated=True)._repr_png_()

    def clear(self):
        self._initialize_annotated_array()
        self._annotated_array.data = self.copy().data

    def draw_box(self, box, color=(255, 0, 0), width=2):
        self._initialize_annotated_array()
        if isinstance(color[0], float):
            color = tuple(map(int, np.array(color[:3]) * 255))
        if hasattr(box, "bounding_box"):
            box = box.bounding_box
        elif hasattr(box, "get_box"):
            box = box.get_box()
        elif hasattr(box, "get_outer_box"):
            box = box.get_outer_box()
        if isinstance(box, tuple):
            box = BoundingBox(*box)
        cv2.rectangle(
            self._annotated_array, (box.x1, box.y1), (box.x2, box.y2), color, width
        )

    def as_pil_image(self, full=False, annotated=False):
        image = Image.fromarray(self._annotated_array if annotated else self)
        if self.box and not full:
            image = image.crop((self.box.x1, self.box.y1, self.box.x2, self.box.y2))
        return image

    def subimage(self, box, relative_to_page=False):
        if relative_to_page or not self.box:
            offset_x = 0
            offset_y = 0
        else:
            offset_x = self.box.x1
            offset_y = self.box.y1
        return self[
            box.x1 + offset_x : box.x2 + offset_x,
            box.y1 + offset_y : box.y2 + offset_y,
            :,
        ]
