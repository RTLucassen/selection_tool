# Selection Tool
A graphical user interface for selection of WSI scans in Python using 
[PyQt5](https://www.riverbankcomputing.com/software/pyqt/).

## Installing the Selection Tool
The WSI selection tool can be installed from GitHub:
```console
$ pip install git+https://github.com/RTLucassen/slide_selection_tool
```

## Example
A minimal example of how the selection tool can be used.
```
import pandas as pd
from selection_tool import SelectionTool

# load dataframe with 
df = pd.load_json(r'path/to/file.json')

# start the selecting WSI scans
SelectionTool(df)
```

## Input
The tool expects a Pandas dataframe as input. This dataframe should at least 
have two columns, 'description' and 'slides', with as rows the information 
for each specimen. The 'description' (str) is displayed on the right side 
of the window to provide the user with more information about the specimen.
The 'slides' (dict) contains all other information about the specimen, such as
the paths to all scans and the staining type. 
A minimum example is provided below:
```
example_dictionary = {
    'slides': [{
        'pa_number': 'T23-00001', 
        'specimen_nr': 'I', 
        'block': '1', 
        'staining': 'HE', 
        'scan': [{
            'base_dir': 'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL_PACS': ['thumbnail.jpeg'],
                'SLIDE': [
                    'slide.4.dcm', 
                    'slide.3.dcm', 
                    'slide.2.dcm', 
                    'slide.1.dcm',
                ],
            }
        },
        {
        'pa_number': 'T23-00002', 
        'specimen_nr': 'II', 
        'block': '1', 
        'staining': 'SOX10', 
        'scan': [{
            'base_dir': 'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL_PACS': ['thumbnail.jpeg'],
                'SLIDE': ['slide.ndpi'],
            },
            {
            'base_dir': 'C:\Users\path\to\directory', 
            'files': {
                'THUMBNAIL_PACS': ['thumbnail.jpeg'],
                'SLIDE': ['slide_v2.ndpi'],
            }
        }],
    }],
}
```