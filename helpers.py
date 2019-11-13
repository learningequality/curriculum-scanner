from config import BULLET_THRESHOLD

class BoundingBox(object):
	def __init__(self, x0, x1, y0, y1):
		self.x0 = x0
		self.x1 = x1
		self.y0 = y0
		self.y1 = y1


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
			min(word.bounding_box.x0 for word in self.words),
			max(word.bounding_box.x1 for word in self.words),
			min(word.bounding_box.y0 for word in self.words),
			max(word.bounding_box.y1 for word in self.words)
		)

	def get_text(self):
		return " ".join([word.text for word in self.words])

	def combine_line(self, line):
		self.words.extend(line.words)

	def extract_bullet(self):
		for index, word in enumerate(self.words[:-1]):
			if self.words[index + 1].bounding_box.x0 - word.bounding_box.x1 > BULLET_THRESHOLD:
				bullet_words = self.words[:index + 1]
				self.words = self.words[index:]
				return Word(
					" ".join([w.text for w in bullet_words]),
					BoundingBox(
						min(word.bounding_box.x0 for word in bullet_words),
						max(word.bounding_box.x1 for word in bullet_words),
						min(word.bounding_box.y0 for word in bullet_words),
						max(word.bounding_box.y1 for word in bullet_words)
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
			min(line.x0 for line in lines),
			max(line.x1 for line in lines),
			min(line.y0 for line in lines),
			max(line.y1 for line in lines),
		)

	def get_text(self, separator="\n"):
		return separator.join([line.get_text() for line in self.lines])
