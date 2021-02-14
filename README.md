
# Curriculum Scanner
Uses a scan of a curriculum book or pdf to generate a csv structure

## Getting Started

You'll need to install the following libraries first:
* [poppler](https://poppler.freedesktop.org/)
* [Python](https://www.python.org/downloads/)
* [pip](https://pip.pypa.io/en/stable/installing/)

Next, install the requirements
 `pip install -r requirements.txt`

You are now ready to start using the CurriculumScanner class!


## The CurriculumScanner Class

The CurriculumScanner class reads the data from running `process_scans.py`. To use this class, you will need to instantiate an object first:

```
from scanner import CurriculumScanner

scanner = CurriculumScanner("<path-to-file>")
```
Note: you may get an error if the Google Vision API hasn't been run on the specified file. To resolve this, you will need to run `CurriculumScanner.process("path-to-file")`. This accepts png, jpg, and pdf files. If you would like to change the detection settings, you'll need to update `config.py`



#### CurriculumScanner.pages
If you would like to access the data directly, you can use the `scanner.pages` attribute. The data will be formatted as the following:

```
[
	{
	    "columns": [
	      [starting point, ending point],
	      ...
	    ],
	    "file": "path/to/page/data.json",
	    "image": "path/to/image.png,
	    "boxes": "path/to/image/with/boxes.png"
	}
]
```


#### Individual page data
Each item in this list will have a path to the corresponding page data, which is the serialized version of the data returned from the [Google Vision API](https://cloud.google.com/vision/docs/). The basic hierarchy is as follows:

```
{
	"pages": [{
		"blocks": [{
			"paragraphs": [{
				"words": [{
					"symbols": {...}
				}]
			}]
		}]
	}]
}
```

If you would like to see each structure's bounds, a visual guide has been generated for you under the `boxes` field under the `scanner.pages` data.
* Blocks = red
* Paragraphs = blue
* Words = yellow

##### Accessing the data
To access this data, you can use the `scanner.get_page_data(page number)` method. Alternatively, if you are iterating through the pages, you can use the `scanner.get_next_page()` function.
```
for page in scanner.get_next_page():
    # Do something with page data
```

In some cases, you may want to access the page blocks in a certain order as they appear on the page. To do this, you can use the `scanner.get_blocks_by_order(page_number, order=BlockOrder)` function.

```
from scanner import BlockOrder

for page_number, page in enumerate(scanner.get_next_page()):
  blocks = scanner.get_blocks_by_order(page_number, order=BlockOrder.LEFTRIGHT)
```

The BlockOrder enum has the following options:
* TOPBOTTOM to read from top to bottom
* BOTTOMTOP to read from the bottom to the top
* LEFTRIGHT to read from left to right
* RIGHTLEFT to read from right to left

---
### Additional Methods

#### text_within
If you would like to get the text that is within a certain boundary, use `scanner.text_within`
```
	# To get text within the box (1, 2) (1, 3) (5, 2) (5, 3) on the first page
	text = scanner.text_within(0, x0=1, y0=2, x1=5, y1=3)
```

#### find_text_matches
If you would like to find where a text appears across the pages, you can use the `scanner.find_text_matches(text)` method.

```
	matches = scanner.find_text_matches('text to find')
```

This will return a list of where each match is found
```
[
  {
    "page": int,
    "block": int,
    "paragraph": int,
    "word": int,
    "bounds": [
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int}
    ]
  }
]
```

#### find_regex_matches
If you would like to find where a regex appears across the pages, you can use the `scanner.find_regex_matches(regex)` method.

```
	matches = scanner.find_text_matches(r'\d+\.\d+\.\d+\.')
```

This will return a list of where each match is found
```
[
  {
    "page": int,
    "block": int,
    "paragraph": int,
    "word": int,  # If a word matches the regex
    "text": str,
    "bounds": [
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int},
      {"x": int, "y": int}
    ]
  }
]
```


#### draw_boxes
If you would like to draw boxes where the OCR bounds are, use the `scanner.draw_boxes(page_number)` method.

```
	image = scanner.draw_boxes(0)  # Draw boxes for page 0
```

This will return an image of the boxes drawn, which can be shown with `image.show()`

If you would like to draw other boxes, you can create a dict with the relevant bounds data. For instance:
```
bound = {
	'vertices': [
		{'x': int, 'y': int},
		{'x': int, 'y': int},
		{'x': int, 'y': int},
		{'x': int, 'y': int},
	]
}

image = scanner.get_page_image(0)

scanner.draw_boxes(image, bound)
```

#### detect_columns

To get column x_ranges, you may use the `scanner.detect_columns(page_number)` method.

```
  columns = scanner.detect_columns(0)  # Get column ranges for page 0
```

For example, if the page has two columns, the data may look something like this:
```
[
	(0, 100),   # First column spans from 0-100px
	(120, 200), # Second column spans from 120-200px
]
```

__Please note__: This code isn't guaranteed to work for all pages





## Chunked workflow
In order to simplify the curriculum digitization process, we'll split the scanned
documents into individual chunks that can later be digitized via crowdsourcing.


#### Create the folder hierarchy for the document

    Document / Chapter / Section / Topic /
    e.g. 
    KICDvolumeII_KICD secondary curriculum volume II/01_Mathematics/01_Form One/13.0.0/

  - Place the source document PDF in `Document/inputs/` directory
  - Each name consists of a short identifier followed by `_` followed by the title.
  - Directories for Chapter and Section must be manually created
  - For KICD topics directories the helper script `mkKICDtopics.py` can be used
    e.g. `mkKICDtopics.py --first=1 --last=23` to create sequentially numbered
    empty folders `1.0.0` through `23.0.0`


#### Manually extract the chunks for topic document

  - Using a PDF tool (Preview on Mac) select a region that contains a given topic
    and save to a separate chunk file, placing it in the appropriate Topic/ dir
  - Repeat for remaining chunks from the topic (make sure sequentially numbered)


#### Rename and convert PDF chunks into PNG format
Run the following script:

    ./scripts/renameandconvertfiles.py  --recursive="chunkedscans/KICDvolumeII_KICD secondary curriculum volume II"

  - This will rename all PDFs found in the topic dirs into standard, sequential filenames
  - Every PDF will be converted to high-res PNG (for OCR) and low-res PNG (for display in UI)


#### Process chunks using OCR
Next we run all the chunks through the Cloud Vision API to extract the text:

    ./scripts/process_chunks.py  --recursive="chunkedscans/KICDvolumeII_KICD secondary curriculum volume II"

This step will produce the following outputs:
  - `{ch}_{sec}_{topic}_chunk{chunkid}_ocr.json` with detailed OCR information
    that includes text and positions
  - `{ch}_{sec}_{topic}_chunk{chunkid}_ocr.txt` the text extracted from individual chunks
  - `{ch}_{sec}_{topic}_combined.txt` for the text from the whole topic

