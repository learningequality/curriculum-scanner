import cv2
import numpy as np
import scipy
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import argrelextrema

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
    # extract by template images
    bullets = get_template_matches(img_rgb, "bullet", 0.8)
    dashes_large = get_template_matches(img_rgb, "dash_large", 0.6)
    dashes_small = get_template_matches(img_rgb, "dash_small", 0.55)

    # join dash matches together, and remove things that are actually bullets
    dashes = (dashes_large + dashes_small) - bullets

    # shrink down the box sizes to fit actual bullet portion, and turn into Words
    return [Word("•", bullet.shrunk(0.25)) for bullet in bullets] + [
        Word("-", dash.shrunk(0.2, axis="x").shifted(2, 0)) for dash in dashes
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
        cluster_overlap = 0.2

        # loop over the existing clusters to find the one with the most overlap
        for i, cluster in enumerate(clusters):
            overlap = word.bounding_box.overlap(cluster["box"], axis="y")
            if overlap > cluster_overlap:
                cluster_overlap = overlap
                cluster_i = i

        if cluster_i is None:  # if no overlapping cluster was found, create a new one
            clusters.append({"box": word.bounding_box, "words": [word]})
        else:  # if we found the cluster with the largest overlap, add to that
            # bullets should only be the starts of clusters, so toss false positives
            if word.text in ["•", "-"]:
                continue
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

    items = ItemList([])
    for cluster in clusters:
        # if not cluster["words"]:
        line = Line(words=cluster["words"])
        bullet = line.extract_bullet_by_pattern()
        items.append(Item(lines=[line], bullet=bullet))

    column_box = items.get_box(include_bullet=True).expanded(0.02)

    for item in items:
        item.lines[0].column_box = column_box

    remove_empty_lines_and_items(items)

    return items


def smooth(x, window_len):
    s = np.r_[x[window_len - 1 : 0 : -1], x, x[-1:-window_len:-1]]
    w = np.hanning(window_len)
    y = np.convolve(w / w.sum(), s, mode="valid")
    return y


def determine_column_bounding_boxes(
    page_data, smoothing_granularity=6, plot_density=False, **kwargs
):
    words = list(extract_word_list(page_data))
    wordboxes = BoundingBoxSet([word.bounding_box for word in words])
    outer = wordboxes.get_outer_box()

    page_width = page_data["pages"][0]["width"]
    width = outer.width()
    height = outer.height()
    start_x = outer.x1
    end_x = outer.x2

    # scan with vertical boxes across the page, counting the number of intersected words
    raw_intersections = np.zeros(outer.x2)
    for x in range(start_x, end_x):
        divider_box = BoundingBox(x - 1, 0, x + 1, height)
        raw_intersections[x] = len(
            [box for box in wordboxes if divider_box.overlap(box)]
        )

    # smooth out the resulting curve, in order to be able to search for minima
    window_len = int(width / smoothing_granularity)
    intersections = smooth(raw_intersections, window_len=window_len)[
        int(window_len / 2) : -int(window_len / 2)
    ]

    # find the local minima in the smoothed word intersection graph
    boundaries = scipy.signal.find_peaks(-intersections, **kwargs)[0]
    boundaries = (
        [start_x]
        + [ind for ind in boundaries if ind > start_x and ind < end_x]
        + [end_x]
    )

    # use these boundaries to create bounding boxes for the columns
    columnboxes = BoundingBoxSet([])
    for i in range(len(boundaries) - 1):
        columnbox = BoundingBox(
            boundaries[i], outer.y1, boundaries[i + 1], outer.y2
        ).expanded(0.02, axis="x")
        columnboxes.append(columnbox)

    # get "block" boxes from original OCR data, and identify blocks not fitting in columns
    blocks = get_original_ocr_block_boxes(page_data)
    lone_blocks = [
        block for block in blocks if not any([block in col for col in columnboxes])
    ]

    columns = BoundingBoxSet([])
    for columnbox in columnboxes:
        columnwords = BoundingBoxSet([])
        for wordbox in wordboxes:
            # only include words that are in the column and not in a lone block
            if wordbox in columnbox and not any(
                [wordbox in lone_block for lone_block in lone_blocks]
            ):
                columnwords.append(wordbox)
        columns.append(columnwords.get_outer_box())

    if plot_density:
        plt.rcParams["figure.figsize"] = (17, 2)
        plt.axes().get_yaxis().set_visible(False)
        plt.plot(intersections)
        plt.plot(raw_intersections)
        plt.xlim(page_width * 0.01, page_width * 0.99)
        plt.margins(0, 0)
        for boundary in boundaries:
            plt.plot([boundary, boundary], [0, max(intersections)], color="green")
        plt.show()

    # add the lone block boxes into the appropriate position in the column list
    for block in lone_blocks:
        found_pos = False
        for i, column in enumerate(columns):
            if (block.x2 < column.x1) or (
                (block.x1 < column.x2) and (block.y2 < column.y1)
            ):
                columns.insert(i, block)
                found_pos = True
                break
        if not found_pos:
            columns.append(block)

    return columns


def apply_brightness_contrast(input_img, brightness=0, contrast=0):

    if not isinstance(input_img, np.ndarray):
        input_img = np.array(input_img)

    if brightness != 0:
        if brightness > 0:
            shadow = brightness
            highlight = 255
        else:
            shadow = 0
            highlight = 255 + brightness
        alpha_b = (highlight - shadow) / 255
        gamma_b = shadow

        buf = cv2.addWeighted(input_img, alpha_b, input_img, 0, gamma_b)
    else:
        buf = input_img.copy()

    if contrast != 0:
        f = 131 * (contrast + 127) / (127 * (131 - contrast))
        alpha_c = f
        gamma_c = 127 * (1 - f)

        buf = cv2.addWeighted(buf, alpha_c, buf, 0, gamma_c)

    return buf


def calculate_total_darkness(img, threshold=0.7):
    orig = img
    img = apply_brightness_contrast(img, 30, 40)
    if img is None:
        print("WARNING: image null after applying contrast/brightness")
        img = orig
    gray = 1 - np.array(img) / 255
    gray[gray < threshold] = 0
    gray[gray >= threshold] = 1
    gray[np.isnan(gray)] = 0
    return gray.sum()


def render_text_box_to_img(text, fontsize=14):
    img = Image.new("RGB", (1000, 50), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("times-new-roman.ttf", fontsize)
    d.text((0, 0), text, font=font, fill=(0, 0, 0))
    return img


def get_simulated_darkness(text, fontsize=14):
    img = render_text_box_to_img(text, fontsize=fontsize)
    return calculate_total_darkness(img)


def get_simulated_darkness_with_height_calibration(text, text_height):
    sim_height = 0
    fontsize = 1
    while sim_height <= text_height:
        fontsize += 6
        img = render_text_box_to_img()
        sim_height = max(np.where(np.array(img).mean(2).mean(1) < 255)[0])
    return calculate_total_darkness(img)


def get_avg_word_darkness(line, img):
    darknesses = []
    for word in line.words:
        subimg = word.bounding_box.shrunk(0.1, axis="y").get_subimage(img)
        darknesses.append(calculate_total_darkness(subimg))
    return np.mean(darknesses)


def simulate_avg_word_darkness(line):
    darknesses = []
    for word in line.words:
        darknesses.append(get_simulated_darkness(word.text))
    return np.mean(darknesses)


def annotate_lines_with_font_weight(items, img):
    for item in items:
        for line in item.lines:
            weight = get_avg_word_darkness(line, img) / simulate_avg_word_darkness(line)
            if weight <= 0 or np.isnan(weight):
                weight = None
            line.fontweight = weight


def get_categorical_color(index, colormap=plt.cm.Dark2):
    cmap = colormap(index)
    return tuple(map(int, np.array(cmap[:3]) * 255))


def annotate_items_with_tab_levels_for_kicd(
    all_items,
    same_level_threshold=0.025,
    same_fontweight_threshold=0.25,
    print_debug_info=False,
):

    tabs = 0
    bullet_type = ""
    last_bullet = ""
    last_bullet_type = ""
    last_bullet_indentation = 0
    last_item_indentation = 0
    last_fontweight = None
    relative_fontweight = None
    relative_fontweight_diff = 0

    item_indentation_list = []
    bullet_indentation_list = []
    tabs_list = []

    for item in all_items:

        box = item.get_box(include_bullet=True)
        bullet = item.bullet.text if item.bullet else ""
        bullet_type = ""
        bullet_indentation = item.get_indentation(include_bullet=True)
        item_indentation = item.get_indentation(include_bullet=False)

        # calculate relative fontweight
        fontweight = item.average_fontweight()
        if fontweight is not None and last_fontweight is not None:
            relative_fontweight_diff = fontweight - last_fontweight
            if abs(relative_fontweight_diff) < same_fontweight_threshold:
                relative_fontweight = "same"
            elif relative_fontweight_diff > 0:
                relative_fontweight = "bolder"
            else:
                relative_fontweight = "less_bold"

        # calculate the relative indentation between the last item and this one
        relative_indent_diff = bullet_indentation - last_bullet_indentation
        if abs(relative_indent_diff) < same_level_threshold:
            relative_indent = "same"
        elif relative_indent_diff > (same_level_threshold * 2):
            relative_indent = "very_indented"
        elif relative_indent_diff > same_level_threshold:
            relative_indent = "somewhat_indented"
        elif relative_indent_diff < (-same_level_threshold * 2):
            relative_indent = "very_dedented"
        elif relative_indent_diff < -same_level_threshold:
            relative_indent = "somewhat_dedented"

        # determine the "type" of the bullet
        if "." in bullet:
            bullet_type = "dotted"
        elif bullet == "•":
            bullet_type = "bullet"
        elif bullet == "-":
            bullet_type = "dash"
        elif ")" in bullet:
            bullet_type = "letter"
        elif bullet:
            bullet_type = "unknown"
        else:
            bullet_type = ""

        def maybeprint(*args):
            if print_debug_info:
                print(
                    *args,
                    relative_indent,
                    relative_indent_diff,
                    relative_fontweight,
                    relative_fontweight_diff
                )

        if bullet_type == "dotted":
            # We know that in KICD these dotted numeric bullets are always top-level.
            maybeprint("DOTTED")
            tabs = 0

        elif last_bullet_type == "dotted" and bullet_type != "dotted":
            # Stuff that comes after a dotted numeric bullet should always be 2nd level.
            maybeprint("POSTDOTTED")
            tabs = 1

        elif bullet_type == last_bullet_type:
            # Bullet types are the same, or neither had a bullet.
            # Here, err on the side of assuming they're at the same level, unless very different.
            # Except also assume that bold text is less indented than non-bold text.
            maybeprint("SAMETYPE")
            if relative_fontweight == "bolder":
                tabs -= 1
            if relative_fontweight == "less_bold":
                tabs += 1
            if relative_indent == "very_dedented":
                tabs -= 1
            elif relative_indent == "very_indented":
                tabs += 1

        elif not bullet_type and last_bullet_type:
            # The last one had a bullet, this one doesn't.
            # Here, we assume it's going up a level, unless the text is indented.
            maybeprint("BULLETLOSS")
            if relative_indent in ["somewhat_indented", "very_indented"]:
                tabs += 1
            else:
                tabs -= 1

        elif bullet_type and not last_bullet_type:
            # The last one had no bullet, this one does.
            # Here, we assume it's going down a level, unless the text is dedented.
            maybeprint("BULLETGAIN")
            if relative_indent in ["somewhat_dedented", "very_dedented"]:
                tabs -= 1
            else:
                tabs += 1

        else:
            # If we got here, it means the type of bullet changed between last item and this one.
            # We err on the side of assuming that the level has changed one way or another, but maybe not.
            maybeprint("NEWTYPE")
            if relative_indent in ["somewhat_indented", "very_indented"]:
                tabs += 1
            elif relative_indent in ["somewhat_dedented", "very_dedented"]:
                tabs -= 1

        # store the tab level onto the item for later use
        item.tabs = tabs

        if print_debug_info:
            print(
                "{}{}{}".format(
                    "\t" * tabs, bullet + " " if bullet else "", item.get_text()
                )
            )

        # remember the info about this item, so we can compare with the next one
        last_bullet_type = bullet_type
        last_bullet = bullet
        last_bullet_indentation = bullet_indentation
        last_item_indentation = item_indentation
        last_fontweight = fontweight


def remove_empty_lines_and_items(items):
    for item in items:
        item.lines = [line for line in item.lines if len(line.words) > 0]
    for i, item in reversed(list(enumerate(items))):
        item.lines = [line for line in item.lines if len(line.words) > 0]
        if len(item.lines) == 0:
            items.pop(i)


def get_original_ocr_block_boxes(page_data):
    blocks = page_data["pages"][0]["blocks"]
    return BoundingBoxSet(
        [
            vertices_to_bounding_box(block["bounding_box"]["vertices"])
            for block in blocks
        ]
    )
