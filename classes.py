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
