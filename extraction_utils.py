import cv2
import numpy as np
import scipy
from scipy.signal import argrelextrema
from matplotlib import pyplot as plt

from classes import BoundingBox, BoundingBoxSet, Word, Line, Item, ItemList


def get_template_matches(img_rgb, template_name, threshold):

    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    template = cv2.imread("templates/{}.png".format(template_name), 0)
    w, h = template.shape[::-1]

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)

    return BoundingBoxSet(
        [BoundingBox(pt[0], pt[1], pt[0] + w, pt[1] + h) for pt in zip(*loc[::-1])]
    ).deduplicate()


def get_bullets_by_template(img_rgb):
    bullets = get_template_matches(img_rgb, "bullet", 0.8)
    dashes_large = get_template_matches(img_rgb, "dash_large", 0.65)
    dashes_small = get_template_matches(img_rgb, "dash_small", 0.6)
    dashes = (dashes_large + dashes_small) - bullets
    return [Word("•", bullet) for bullet in bullets] + [
        Word("-", dash) for dash in dashes
    ]


def vertices_to_bounding_box(vertices):
    x1 = min(v["x"] for v in vertices)
    y1 = min(v["y"] for v in vertices)
    x2 = max(v["x"] for v in vertices)
    y2 = max(v["y"] for v in vertices)
    return BoundingBox(x1, y1, x2, y2)


def extract_word_list(page_data):
    for page in page_data["pages"]:
        for block in page["blocks"]:
            for paragraph in block["paragraphs"]:
                for word in paragraph["words"]:
                    box = vertices_to_bounding_box(word["bounding_box"]["vertices"])
                    yield Word(
                        text="".join([s["text"] for s in word["symbols"]]),
                        bounding_box=box,
                    )


def extract_single_line_items_from_column(page_data, column_box=None, bullets=[]):

    # extract all the words in the page
    words = list(extract_word_list(page_data)) + bullets

    # excluding any that aren't in the column, if box was provided
    if column_box:
        words = [word for word in words if word.bounding_box in column_box]

    # build up a list of the clusters as we find them
    clusters = []

    # sort words by leftmost X value, so that we seed the initial clusters with vertical diversity
    words = sorted(words, key=lambda word: word.bounding_box.x1)

    # loop over the words and add them one by one to the best cluster, or create a new cluster
    for word in words:
        # keep track of the most overlapping cluster, ignoring any with < 0.1 overlap
        cluster_i = None
        cluster_overlap = 0.1

        # loop over the existing clusters to find the one with the most overlap
        for i, cluster in enumerate(clusters):
            overlap = word.bounding_box.overlap(cluster["box"], axis="y")
            if overlap > cluster_overlap:
                cluster_overlap = overlap
                cluster_i = i

        if cluster_i is None:
            # if no overlapping cluster was found, create a new one
            clusters.append({"box": word.bounding_box, "words": [word]})
        else:
            # if we found the cluster with the largest overlap, add to that
            cluster = clusters[cluster_i]
            cluster["box"] = cluster["box"] | word.bounding_box
            cluster["words"].append(word)

    # sort the clusters (lines) by top Y value to put them in sequential order
    clusters = sorted(clusters, key=lambda cluster: cluster["box"].y1)

    # remove duplicate bullets
    for cluster in clusters:
        if len(cluster["words"]) < 2:
            continue
        w1, w2 = cluster["words"][:2]
        if (
            w1.bounding_box.overlap(w2.bounding_box) > 0.05
            and w1.text.strip() == w2.text.strip()
        ):
            cluster["words"].pop(1)

    return ItemList(
        [Item(lines=[Line(words=cluster["words"])]) for cluster in clusters]
    )


def smooth(x, window_len):
    s = np.r_[x[window_len - 1 : 0 : -1], x, x[-1:-window_len:-1]]
    w = np.hanning(window_len)
    y = np.convolve(w / w.sum(), s, mode="valid")
    return y


def determine_column_bounding_boxes(
    page_data, smoothing_granularity=6, plot_density=False
):
    words = list(extract_word_list(page_data))
    wordboxes = BoundingBoxSet([word.bounding_box for word in words])
    outer = wordboxes.get_outer_box()

    width = outer.width()
    height = outer.height()
    start_x = outer.x1
    end_x = outer.x2

    raw_intersections = np.zeros(outer.x2)

    for x in range(start_x, end_x):
        divider_box = BoundingBox(x - 1, 0, x + 1, height)
        raw_intersections[x] = len(
            [box for box in wordboxes if divider_box.overlap(box)]
        )

    window_len = int(width / smoothing_granularity)
    intersections = smooth(raw_intersections, window_len=window_len)[
        int(window_len / 2) : -int(window_len / 2)
    ]

    boundaries = scipy.signal.find_peaks(-intersections)[0]
    boundaries = (
        [start_x]
        + [ind for ind in boundaries if ind > start_x and ind < end_x]
        + [end_x]
    )

    if plot_density:
        plt.plot(intersections)
        plt.plot(raw_intersections)
        plt.rcParams["figure.figsize"] = (15, 2)
        plt.show()

    columns = []
    for i in range(len(boundaries) - 1):
        columnbox = BoundingBox(boundaries[i], outer.y1, boundaries[i + 1], outer.y2)
        columnwords = BoundingBoxSet([])
        for wordbox in wordboxes:
            if wordbox in columnbox:
                columnwords.append(wordbox)
        columns.append(columnwords.get_outer_box())

    return columns
