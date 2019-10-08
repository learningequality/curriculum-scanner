SYMBOL_STRUCTURE = {
  'name': 'symbols',
  'fields': ['confidence', 'text'],
  'objects': ['bounding_box', 'property']
}

WORD_STRUCTURE = {
  'name': 'words',
  'fields': ['confidence'],
  'objects': ['bounding_box', 'property'],
  'list': SYMBOL_STRUCTURE
}

PARAGRAPH_STRUCTURE = {
  'name': 'paragraphs',
  'fields': ['confidence'],
  'objects': ['bounding_box', 'property'],
  'list': WORD_STRUCTURE
}

BLOCK_STRUCTURE = {
  'name': 'blocks',
  'fields': ['block_type', 'confidence'],
  'objects': ['bounding_box', 'property'],
  'list': PARAGRAPH_STRUCTURE
}

PAGE_STRUCTURE = {
  'name': 'pages',
  'fields': ['confidence', 'height', 'width'],
  'objects': ['property'],
  'list': BLOCK_STRUCTURE
}

STRUCTURE = {
  'name': 'overall',
  'fields': ['text'],
  'objects': [],
  'list': PAGE_STRUCTURE
}

WRITE_DIRECTORY = 'scans'
ORIENTATION_DETECTION_THRESHOLD = 10  # 10 characters minimum returns more accurate results
