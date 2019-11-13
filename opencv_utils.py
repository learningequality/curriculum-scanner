import cv2
import numpy as np

from classes import BoundingBox, BoundingBoxSet


def get_template_matches(img_rgb, template_name, threshold):

    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    template = cv2.imread("templates/{}.png".format(template_name), 0)
    w, h = template.shape[::-1]

    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)

    return BoundingBoxSet(
        [BoundingBox(pt[0], pt[1], pt[0] + w, pt[1] + h) for pt in zip(*loc[::-1])]
    )


def get_bullets_by_template(img_rgb):
    bullets = get_template_matches(img_rgb, "bullet", 0.8)
    dashes_large = get_template_matches(img_rgb, "dash_large", 0.65)
    dashes_small = get_template_matches(img_rgb, "dash_small", 0.65)
    dashes = (dashes_large + dashes_small) - bullets
    return bullets, dashes
