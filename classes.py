from config import BULLET_THRESHOLD

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
        if x2 < x1 or y2 < y1:
            return None
        return BoundingBox(x1, y1, x2, y2)

    def __or__(self, other):
        # returns the union of the bounding boxes (box that contains both)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        x2 = max(self.x2, other.x2)
        y2 = max(self.y2, other.y2)
        return BoundingBox(x1, y1, x2, y2)

    def overlap(self, other):
        """
        Calculate the Intersection over Union (IoU) of two bounding boxes.
        Adapted from: https://stackoverflow.com/questions/25349178/calculating-percentage-of-bounding-box-overlap-for-image-detector-evaluation
        """

        intersection = self & other
        if intersection is None:
            return 0.0
        intersection_area = intersection.area()

        # compute the intersection over union by taking the intersection area and dividing it
        # by the sum of the two areas minus the intersection area
        return intersection_area / float(self.area() + other.area() - intersection_area)


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
            max(word.bounding_box.y2 for word in self.words)
        )

    def get_text(self):
        return " ".join([word.text for word in self.words])

    def extract_bullet(self):
        for index, word in enumerate(self.words[:-1]):
            if self.words[index + 1].bounding_box.x1 - word.bounding_box.x2 > BULLET_THRESHOLD:
                bullet_words = self.words[:index + 1]
                self.words = self.words[index:]
                return Word(
                    " ".join([w.text for w in bullet_words]),
                    BoundingBox(
                        min(word.bounding_box.x1 for word in bullet_words),
                        min(word.bounding_box.y1 for word in bullet_words),
                        max(word.bounding_box.x2 for word in bullet_words),
                        max(word.bounding_box.y2 for word in bullet_words)
                    )
                )


class Item(object):
    lines = None
    bullet = None

    def __init__(self, bullet, lines):
        self.bullet = bullet
        self.lines = lines or []

    def set_bullet(self, bullet):
        self.bullet = bullet

    def add_line(self, line):
        self.lines.append(line)

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
