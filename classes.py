from config import BULLET_THRESHOLD
import numpy as np


class BoundingBox(object):
    def __init__(self, x1, y1, x2, y2):
        assert x1 < x2
        assert y1 < y2
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def center(self):
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    def area(self):
        return (self.x2 - self.x1) * (self.y2 - self.y1)

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
            fontweight: string for fontweight properties (bold | normal)
    """

    words = None
    fontweight = "normal"

    def __init__(self, words, fontweight="normal"):
        self.fontweight = fontweight
        self.words = words or []

    def add_word(self, word):
        self.words.append(word)

    def get_box(self):
        return BoundingBox(
            min(word.bounding_box.x1 for word in self.words),
            min(word.bounding_box.y1 for word in self.words),
            max(word.bounding_box.x2 for word in self.words),
            max(word.bounding_box.y2 for word in self.words),
        )

    def get_text(self):
        return " ".join([word.text for word in self.words])

    def extract_bullet(self):
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
                bullet_words = self.words[:index + 1]
                self.words = self.words[index + 1:]
                return Word(
                    " ".join([w.text for w in bullet_words]),
                    BoundingBox(
                        min(word.bounding_box.x1 for word in bullet_words),
                        min(word.bounding_box.y1 for word in bullet_words),
                        max(word.bounding_box.x2 for word in bullet_words),
                        max(word.bounding_box.y2 for word in bullet_words),
                    ),
                )


class Item(object):
    lines = None
    bullet = None

    def __init__(self, lines, bullet=None):
        self.bullet = bullet
        self.lines = lines or []

    def set_bullet(self, bullet):
        self.bullet = bullet

    def add_lines(self, lines):
        self.lines.extend(lines)

    def get_box(self):
        lines = [line.get_box() for line in self.lines]
        return BoundingBox(
            min(line.x1 for line in lines),
            min(line.y1 for line in lines),
            max(line.x2 for line in lines),
            max(line.y2 for line in lines),
        )

    def get_text(self, separator="\n"):
        return separator.join([line.get_text() for line in self.lines])


class ItemList(list):
    def get_box(self):
        items = [item.get_box() for item in self]
        return BoundingBox(
            min(item.x1 for item in items),
            min(item.y1 for item in items),
            max(item.x2 for item in items),
            max(item.y2 for item in items),
        )

    def add_item(self, item):
        if item.lines:
            self.append(item)

    def combine_lines(self):
        new_items = ItemList([])
        current_item = Item([])
        for item in self:
            if item.bullet:
                new_items.add_item(current_item)
                current_item = Item([], bullet=item.bullet)
            current_item.add_lines(item.lines)

        new_items.add_item(current_item)
        return new_items
