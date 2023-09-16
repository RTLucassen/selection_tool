# Selection Tool
A graphical user interface for selecting whole slide images (WSIs) in Python 3.9+ using 
[PyQt5](https://www.riverbankcomputing.com/software/pyqt/).
<div align="center">
  <img width="100%" alt="Demo" src=".github\demo.gif">
</div>

The layout of the selection tool consists of three main components: 
- The selection buttons are positioned on the left, showing all WSIs that are available for one specimen at a time. Left-click on a button to select the WSI. 
- The image viewer in the center displays clicked scans. The scroll wheel can be used to zoom in, the left mouse button to pan around, and the right mouse button to reset the view. Currently, the viewer can only display WSIs at a low or medium magnification.
- The text description and comments window are positioned on the right, together with the buttons to go the previous or next case.

## Installing the Selection Tool
The WSI selection tool can be installed from GitHub:
```console
$ pip install git+https://github.com/RTLucassen/selection_tool
```

## Example
A minimal example of how the selection tool can be used.
```
import pandas as pd
from selection_tool import SelectionTool

# load dataframe with 
df = pd.load_json(r'path/to/file.json')

# start selecting WSIs
SelectionTool(df)
```

To test the selection tool, we've provided `example.py` in the root of this repository.
The code in this file code creates a small dataset by downloading 4 WSIs from the GDC data portal (~2.2GB) 
and saving corresponding low magnification thumbnail images. 
The dataset then serves as an example to play around with the selection tool.

## Input
The tool expects a Pandas dataframe as input. This dataframe should at least 
have two columns, `description` and `slides`, with as rows the information 
for each specimen. Other columns are not used by the selection tool,
but if given as part of the input dataframe, 
extra columns will also be included in the output file.
- Each item in the `description` column should be a string with more information about the specimen,
which is displayed to the user on the right side of the window.
- Each item in the `slides` column should be a dictionary containing 
all other information about the specimen, including the pa_number,
specimen number, block number, staining type, and paths to all images. 
A minimal example is provided below:
```
example_slides = {
    'slides': [{
        'pa_number': 'T23-00001', 
        'specimen_nr': 'I', 
        'block': '1', 
        'staining': 'HE', 
        'scan': [{
            'base_dir': r'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL': ['thumbnail.jpeg'],
                'SLIDE': [
                    'slide.4.dcm', 
                    'slide.3.dcm', 
                    'slide.2.dcm', 
                    'slide.1.dcm',
                ],
            }
        }],
    },
    {
        'pa_number': 'T23-00001', 
        'specimen_nr': 'II', 
        'block': '1', 
        'staining': 'SOX10', 
        'scan': [{
            'base_dir': r'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL': ['thumbnail.jpeg'],
                'SLIDE': ['slide.ndpi'],
            },
        },
        {
            'base_dir': r'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL': ['thumbnail_v2.jpeg'],
                'SLIDE': ['slide_v2.ndpi'],
            }
        }],
    }],
}
```
The example dictionary above contains the information for two slides.
The first slide has one scan, which is stored as a DICOM file (with each magnification level as a separate image) and a JPEG thumbnail.
The second slide has two scans, which are both stored as NDPI files with JPEG thumbnails.
