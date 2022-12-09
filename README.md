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
