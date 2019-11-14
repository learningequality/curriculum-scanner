import cv2
import numpy as np

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


def extract_word_list(page_data):
    for page in page_data["pages"]:
        for block in page["blocks"]:
            for paragraph in block["paragraphs"]:
                for word in paragraph["words"]:
                    topleft, _, bottomright, _ = word["bounding_box"]["vertices"]
                    box = BoundingBox(
                        topleft["x"], topleft["y"], bottomright["x"], bottomright["y"]
                    )
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
