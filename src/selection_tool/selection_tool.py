#    Copyright 2022 Ruben T Lucassen, UMC Utrecht, The Netherlands 
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Selection tool

Controls
_________________________________________________
<a>:                            previous specimen
<d>:                                next specimen


Viewer controls
_________________________________________________
Left mouse button press:                  panning
Scroll wheel:                  zooming in and out
Right mouse button click:              reset view
"""

import os
import queue
import sys
import threading
from typing import Callable, Optional

import numpy as np
import pandas as pd
import qdarktheme
import SimpleITK as sitk
from PyQt5 import QtCore, QtGui, QtWidgets
from slideloader import SlideLoader

from ._viewer_utils import QtImageViewer
from ._specimen_utils import Specimen
from ._general_utils import calculate_background_color, calculate_window_geometry, is_HE
from . import fonts


FONTS = [
    'DMSans-Bold.ttf', 
    'DMSans-Regular.ttf',
]


class CustomQPushButton(QtWidgets.QPushButton):
    rightclicked = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

    # overwrite mousePressEvent
    @QtCore.pyqtSlot()
    def mousePressEvent(self, event):       
        super().mousePressEvent(event)
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.RightButton:
                self.rightclicked.emit()


class ScanButton(QtWidgets.QWidget):
    """
    Implementation of widget with scan button and information.
    """

    def __init__(self) -> None:
        """
        Initialize widgets that are part of each scan button.
        """
        super().__init__()

        # define widget for scan image and background color
        self.background = QtWidgets.QLabel()
        self.background.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # define text labels for specimen number and staining method
        self.specimen_label = QtWidgets.QLabel()
        self.specimen_label.setStyleSheet('background-color: transparent')
        self.specimen_label.setFont(QtGui.QFont('DM Sans', 12))
        self.specimen_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
        )
        self.IHC_label = QtWidgets.QLabel()
        self.IHC_label.setStyleSheet('background-color: transparent')
        self.IHC_label.setFont(QtGui.QFont('DM Sans', 12))
        self.IHC_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
        )
        self.score_label = QtWidgets.QLabel()
        self.score_label.setStyleSheet(
            'background-color: transparent; color: rgb(100,180,100); font-weight: bold',
        )
        self.score_label.setFont(QtGui.QFont('DM Sans', 14))
        self.score_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop,
        )
        self.staining_label = QtWidgets.QLabel()
        self.staining_label.setStyleSheet('background-color: transparent')
        self.staining_label.setFont(QtGui.QFont('DM Sans', 12))
        self.staining_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignBottom,
        )

        # define button widget
        self.button = CustomQPushButton()

        # configure layout
        self.__widget_layout = QtWidgets.QGridLayout(self)
        self.__widget_layout.addWidget(self.background, 0, 0, 2, 3)
        self.__widget_layout.addWidget(self.specimen_label, 0, 0, 1, 1)
        self.__widget_layout.addWidget(self.IHC_label, 0, 1, 1, 1)
        self.__widget_layout.addWidget(self.score_label, 0, 2, 1, 1)
        self.__widget_layout.addWidget(self.staining_label, 1, 0, 1, 3)
        self.__widget_layout.addWidget(self.button, 0, 0, 2, 3)


class SelectionWindow(QtWidgets.QWidget):
    """
    Implementation of window for WSI selection.
    """
    # define widget settings
    __window_fraction = 0.65
    __button_fraction = 0.08
    __padding_button = 0.028
    __info_fraction = 0.15
    __padding_info = 0.032
    __correction_fraction = 0.03
    __default_background_color = (245, 245, 245)
    # define other tool settings
    __select_non_HE = True
    __magnification = 5.00
    __load_higher_magnification = False
    __specimen_buffer = (1,10)
    __workers = 2
    # define usability settings
    __reverse_zoom = True

    def __init__(
        self, 
        df: pd.DataFrame,
        screen_size: tuple[int, int],
        starting_index: Optional[int],
        selected_indices: Optional[list],
        selection_threshold: Optional[int],
        select_by_default: bool,
        multithreading: bool,
        is_HE_function: Optional[Callable],
        autoselect_function: Optional[Callable],
        output_path: str,
    ) -> None:
        """
        Initialize selection window instance.

        Args:
            df:  Dataframe with specimen information from archive database.
            screen_size:  Size of computer screen as (width, height).
            starting_index:  Starting case for selection (if None, the starting 
                index will be the last case where at least on slide was selected).
            selected_indices:  List with a selection of indices which are shown. 
                The 'previous' and 'next' buttons go to the index smaller and 
                larger in the list, respectively. (if None, all cases are shown).
            selection_threshold:  Maximum number of selectable scans per specimen
                (None is interpreted as no maximum number).
            select_by_default:  Specifies whether all scans are selected from 
                the start (the selection threshold is overwritten when True).
            multithreading:  Specifies whether higher magnification images are 
                loaded in the background on different threads.
            is_HE_fuction:  Function that returns True when straining name 
                refers to H&E and False otherwise.
            autoselect_function:  Function that returns list with boolean for 
                each scan for the input specimen indicating whether it should 
                be automatically selected or not.
            output_path:  Path to output file to save the selection results.
        """
        super().__init__()
        # define instance attributes
        self.__df = df.replace({np.nan:None})
        self.__screen_size = screen_size
        self.__output_path = output_path
        self.__multithreading = multithreading
        self.__specimens = [
            Specimen(row['slides'], row['description']) for _, row in self.__df.iterrows()
        ]
        self.__max_buttons = max([len(specimen.scans) for specimen in self.__specimens])
        self.__button_size = int(self.__button_fraction*self.__screen_size[0])
        self.__loaded_images = {}
        self.__background_colors = {}
        self.__requested = []
        self.__specimen = None
        self.__specimen_index = 0
        self.__selected_indices = selected_indices
        self.__scoring = {}

        # if an empty list was provided, change to None
        if self.__selected_indices == []:
            self.__selected_indices = None
        # check if the selected indices are all valid
        if self.__selected_indices is not None:
            self.__selected_indices = sorted(list(set(self.__selected_indices)))
            if (min(self.__selected_indices) < 0 or 
                max(self.__selected_indices) > len(self.__df)-1):
                raise ValueError('Atleast one of the selected indices is invalid.')

        # if a starting index was provided, use this index if it is valid
        if starting_index is not None:
            self.__specimen_index = starting_index
            if self.__selected_indices is not None:
                if self.__specimen_index not in self.__selected_indices:
                    raise ValueError(('Argument for starting index is not part '
                                      'of the selected indices.'))
            elif starting_index < 0 or starting_index > len(self.__df)-1:
                raise ValueError('Argument for starting index is invalid.')
        
        # else, if a subset of cases was provided, start from the first index
        elif self.__selected_indices is not None:
            self.__specimen_index = min(self.__selected_indices)

        # else, if scans were already (manually) selected, 
        # start from the last specimen
        elif 'selected_scans' in self.__df:
            for i in reversed(list(range(len(self.__df)))):
                row = self.__df.iloc[i]
                if row['selected_scans'] is not None:
                    # check if any scans were manually selected
                    all_automatically_selected = True
                    for slide in row['selected_scans']['slides']:
                        for scan in slide['scan']:
                            if 'automatically selected' not in scan['flags']:
                                all_automatically_selected = False
                    # if any scans were manually selected, start from this index
                    if not all_automatically_selected:
                        self.__specimen_index = i
                        break
        
        # define attribute for selection by default and check selection threshold
        self.__select_by_default = select_by_default
        if self.__select_by_default and selection_threshold is not None:
            selection_threshold = None
            print(('Warning: The selection threshold was overwritten because'
                ' all scans are selected by default.'))

        # define attribute the maximum number of scans that can be selected and
        # the autoselect function
        if selection_threshold is None:
            self.__selection_threshold = self.__max_buttons
        elif selection_threshold < 1:
            raise ValueError('The selection threshold must be larger than zero.')
        else:
            self.__selection_threshold = selection_threshold
        
        # define the function to determine whether a slide has H&E staining
        # or IHC staining, sort the slides and scans, and add a staining flag
        self.__is_HE = is_HE if is_HE_function is None else is_HE_function
        for specimen in self.__specimens:
            # sort slides
            specimen.sort_slides(self.__is_HE)     
            # add staining flag       
            for scan in specimen.scans:
                flag = 'HE' if self.__is_HE(scan.slide.staining) else 'IHC'
                if flag not in scan.flags:
                    scan.flags.append(flag)
            
        # apply autoselect function or default selection depending on mode
        for specimen in self.__specimens:
            # check if an autoselect function was provided
            if autoselect_function is not None:
                autoselected = autoselect_function(specimen)

                # check if output from the autoselection function is valid
                # if so, apply the autoselection result
                if not isinstance(autoselected, list):
                    raise TypeError(('The autoselect function should provide'
                        ' a list with for each scan a boolean indicating whether'
                        ' the scan is selected or not.'))
                elif len(autoselected) != len(specimen.scans):
                    raise ValueError(('The number of elements in the list'
                        ' provided by the autoselect function is not equal to the'
                        ' number of scans for the specimen.'))
                else:
                    for scan, selected in zip(specimen.scans, autoselected):
                        if scan.selected is None:
                            scan.selected = selected
                            if selected:
                                scan.flags.append('automatically selected')

            # apply default selection mode (all are selected or deselected)
            for scan in specimen.scans:
                if scan.selected is None:
                    scan.selected = self.__select_by_default
                    if scan.selected:
                        scan.flags.append('automatically selected')

        # prepare queue and workers if multithreading is used
        if self.__multithreading:
            # initialize threads
            self.__queue = queue.PriorityQueue()
            
            # define worker
            def worker():
                while True:
                    _, key = self.__queue.get()
                    if key == 'terminate':
                        break
                    elif key[2]:
                        self._load_image(key)
                    else:
                        self._load_thumbail(key)
                    self.__queue.task_done()

            # create workers
            self.__threads = []
            for _ in range(self.__workers):
                self.__threads.append(threading.Thread(target=worker))
                self.__threads[-1].daemon = True
                self.__threads[-1].start()

        # configure window
        self.setWindowTitle('Selection tool')
        self.setGeometry(
            *calculate_window_geometry(self.__screen_size, self.__window_fraction),
        )

        # initialize all widgets
        self._initialize_widgets()

        # define and connect keyboard shortcut
        self.__next_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("D"), self)
        self.__next_shortcut.activated.connect(self._next_case)
        self.__previous_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("A"), self)
        self.__previous_shortcut.activated.connect(self._previous_case)
        self.__score_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("S"), self)
        self.__score_shortcut.activated.connect(self.__score_checkbox.nextCheckState)
        self.__HE_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("H"), self)
        self.__HE_shortcut.activated.connect(self.__HE_checkbox.nextCheckState)

        self.setFocus()

    def _initialize_widgets(self) -> None:
        """
        Initialize widgets and position in the window.
        """
        # define layout for the scroll region
        self.__scroll_layout_buttons = QtWidgets.QFormLayout()
        self.__scroll_layout_buttons.setVerticalSpacing(0)

        # create scan buttons
        self.__scan_buttons = []
        for i in range(self.__max_buttons):
            # create widget, add it to the layout, and store it
            scan_button = ScanButton()
            scan_button.button.setObjectName(str(i))
            scan_button.button.setFixedSize(self.__button_size, self.__button_size)
            scan_button.specimen_label.setMaximumWidth(self.__button_size)
            scan_button.staining_label.setMaximumWidth(self.__button_size)
            scan_button.button.clicked.connect(self._on_left_click)
            scan_button.button.rightclicked.connect(self._on_right_click)
            self.__scroll_layout_buttons.addWidget(scan_button)
            self.__scan_buttons.append(scan_button)

        # define frame for the scroll region and add the layout
        self.__scroll_frame_buttons = QtWidgets.QFrame()
        self.__scroll_frame_buttons.setLayout(self.__scroll_layout_buttons)
        # define the scroll area for the scan buttons
        self.__scroll_area_buttons = QtWidgets.QScrollArea()
        self.__scroll_area_buttons.setWidget(self.__scroll_frame_buttons)
        scroll_width = (self.__button_fraction + self.__padding_button)
        self.__scroll_area_buttons.setFixedWidth(
            int(scroll_width*self.__screen_size[0]),
        )
        self.__scroll_area_buttons.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.__scroll_area_buttons.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        # define case label
        self.__case_label = QtWidgets.QLabel()
        self.__case_label.setFont(QtGui.QFont('DM Sans', 32))
        self.__case_label.mousePressEvent = self._copy

        # define next case button
        self.__next_button = QtWidgets.QPushButton()
        self.__next_button.setStyleSheet('font-weight: bold')
        self.__next_button.setFont(QtGui.QFont('DM Sans', 12))
        self.__next_button.setText('Next')
        self.__next_button.clicked.connect(self._next_case)

        # define next case button
        self.__previous_button = QtWidgets.QPushButton()
        self.__previous_button.setStyleSheet('font-weight: bold')
        self.__previous_button.setFont(QtGui.QFont('DM Sans', 12))
        self.__previous_button.setText('Previous')
        self.__previous_button.clicked.connect(self._previous_case)

        self.__HE_checkbox = QtWidgets.QCheckBox()
        self.__HE_checkbox.setStyleSheet('font-weight: bold')
        self.__HE_checkbox.setFont(QtGui.QFont('DM Sans', 12))
        self.__HE_checkbox.setText('Only H&&E')
        self.__HE_checkbox.setChecked(False)
        self.__HE_checkbox.stateChanged.connect(
            lambda: [self._store_selection(), self._change_widgets()],
        )
        self.__score_checkbox = QtWidgets.QCheckBox()
        self.__score_checkbox.setStyleSheet('font-weight: bold')
        self.__score_checkbox.setFont(QtGui.QFont('DM Sans', 12))
        self.__score_checkbox.setText('Add Score')
        self.__score_checkbox.setChecked(False)
        self.__score_checkbox.stateChanged.connect(self._store_selection)

        # define image visualization frame
        self.__image_viewer = QtImageViewer(self.__reverse_zoom)
        self.__image_viewer.regionZoomButton = None
        self.__image_viewer.zoomOutButton = QtCore.Qt.MouseButton.RightButton
        self.__image_viewer.panButton = QtCore.Qt.MouseButton.LeftButton

        # define information label
        self.__info_label = QtWidgets.QLabel()
        self.__info_label.setFont(QtGui.QFont('DM Sans', 9))
        self.__info_label.setWordWrap(True)
        self.__info_label.setMargin(10)
        self.__info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignJustify)
        self.__info_label.setMinimumWidth(
            int(self.__info_fraction*self.__screen_size[0]),
        )

        # define layout for the scroll region
        self.__scroll_layout_label = QtWidgets.QFormLayout()        
        self.__scroll_layout_label.addWidget(self.__info_label)

        # define frame for the scroll region and add the layout
        self.__scroll_frame_info = QtWidgets.QFrame()
        self.__scroll_frame_info.setLayout(self.__scroll_layout_label)

        # define the scroll area for text
        self.__scroll_area_label = QtWidgets.QScrollArea()
        self.__scroll_area_label.setWidget(self.__scroll_frame_info)
        scroll_width = (self.__info_fraction + self.__padding_info)
        self.__scroll_area_label.setFixedWidth(
            int(scroll_width*self.__screen_size[0])-25,
        )
        self.__scroll_area_label.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.__scroll_area_label.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

        # define text box
        self.__textbox = QtWidgets.QLineEdit(self)
        self.__textbox.setFont(QtGui.QFont('DM Sans', 12))
        self.__textbox.setPlaceholderText('Comments')

        # create widget layout and add widgets to it
        self.__widget_layout = QtWidgets.QGridLayout(self)
        self.__widget_layout.addWidget(self.__case_label, 0, 0, 2, 2)
        self.__widget_layout.addWidget(self.__previous_button, 0, 2)
        self.__widget_layout.addWidget(self.__next_button, 0, 3)
        self.__widget_layout.addWidget(self.__HE_checkbox, 1, 2)
        self.__widget_layout.addWidget(self.__score_checkbox, 1, 3)
        self.__widget_layout.addWidget(self.__scroll_area_buttons, 2, 0, 2, 1)
        self.__widget_layout.addWidget(self.__image_viewer, 2, 1, 2, 1)
        self.__widget_layout.addWidget(self.__scroll_area_label, 2, 2, 1, 2)
        self.__widget_layout.addWidget(self.__textbox, 3, 2, 1, 2)
        
        self._change_widgets()

    def _copy(self, event):
        """
        Copy pa_number to clipboard after right mouse button click.
        """
        self.setFocus()
        # check if the right mouse button was used for clicking
        if event.button() == 2:
            pa_number = self.__specimens[self.__specimen_index].pa_number
            cb = QtWidgets.QApplication.clipboard()
            cb.clear(mode=cb.Clipboard)
            cb.setText(pa_number, mode=cb.Clipboard)

    def _get_background_color(self, key: tuple[int, int, bool]) -> str:
        """
        Get the background color from the dictionary. 
        Return None if the key is not in the dictionary.

        Args:
            key:  Tuple consisting of (specimen index, scan index, boolean that 
                indicates whether the image is loaded in low or higher magnification).
        """
        if key in self.__background_colors:
            return self.__background_colors[key]
        else:
            return self.__default_background_color
        
    def _set_image(self, scan_index: int) -> None:
        """
        Set an image in the main image viewer.

        Args:
            scan_index:  Index integer to indicate scan for specimen.
        """        
        # get the pixmap
        if scan_index is None:
            pixmap = None
        else:
            key = (self.__specimen_index, scan_index, True)
            if key not in self.__loaded_images:
                key = (self.__specimen_index, scan_index, False)
            pixmap = self.__loaded_images[key]

        # check if a pixmap is available
        if pixmap is None:
            self.__image_viewer.clearImage()
            self.__image_viewer.setStyleSheet(
                qdarktheme.load_stylesheet('light'),
            )
        else:
            # set the pixmap
            self.__image_viewer.setImage(pixmap)
            self.__image_viewer.setStyleSheet(
                f'background-color: rgb{self._get_background_color(key)}',
            )
            self.__image_viewer.clearZoom()
        
    def _load_image(self, key: tuple[int, int, bool]) -> None:
        """
        Load higher magnification image on another thread.
        
        Args:
            key:  Tuple consisting of (specimen index, scan index, boolean that 
                indicates whether the image is loaded in low or higher magnification).
        """
        # initialize SlideLoader instance
        loader = SlideLoader({'progress_bar': False, 'multithreading': True})
        
        # check if there are any paths 
        paths = self.__specimens[key[0]].scans[key[1]].paths
        if not len(paths):
            print('Warning: No path(s) for high magnification scan are available.')
            return

        # since DICOM WSI are stored as separate images per magnification,
        # where the largest images are slowest to load, try loading the scan at
        # the desired magnification by adding one more magnification level at a time
        # (because the magnification levels are not known before loading the images)
        subset_paths = []
        loaded = False
        for path in paths:
            subset_paths += [path]
            loader.load_slide(subset_paths)
            # try loading the image at a particular magnification
            try:
                array = loader.get_image(self.__magnification)
            except ValueError: # catch the error if not possible
                pass
            else: # if possible, break out of the loop
                height, width, _ = array.shape
                bytes_per_line = 3 * width
                pixmap = QtGui.QPixmap.fromImage(QtGui.QImage(
                    array.copy(), 
                    width, 
                    height, 
                    bytes_per_line, 
                    QtGui.QImage.Format_RGB888,
                ))
                self.__loaded_images[key] = pixmap
                loaded = True
                break
        
        # if there are paths but the scan was not successfully loaded
        # (e.g., because the specified magnification was unavailable)
        if not loaded:
            print(('Warning: A scan was not successfully loaded. '
                'Check if the magnification was set correctly'))

    def _load_thumbail(self, key: tuple[int, int, bool]) -> None:
        """
        Load thumbnail image on a new thread.
        
        Args:
            key:  Tuple consisting of (specimen index, scan index, boolean that 
                indicates whether the image is loaded in low or higher magnification).
        """
        # check if there are any paths 
        path = self.__specimens[key[0]].scans[key[1]].thumbnail_path
        if path is None:
            self.__loaded_images[key] = None
        else:
            # load thumbnail image
            try:
                array = sitk.GetArrayFromImage(sitk.ReadImage(path))
            except:
                self.__loaded_images[key] = None
                print('Warning: Thumbnail image was not successfully loaded.')
            else:
                # convert image to pixmap
                height, width, _ = array.shape
                bytes_per_line = 3 * width
                pixmap = QtGui.QPixmap.fromImage(QtGui.QImage(
                    array.copy(), 
                    width, 
                    height, 
                    bytes_per_line, 
                    QtGui.QImage.Format_RGB888,
                ))
                self.__background_colors[key] = calculate_background_color(array)
                self.__loaded_images[key] = pixmap

    def _change_widgets(self) -> None:
        """
        Apply changes to widgets when the previous or next specimen is selected.
        """
        # reset instance variables for specific specimen
        self.__specimen = self.__specimens[self.__specimen_index]

        # get the indices of all selected slides
        self.__scan_indices = [
            i for i, scan in enumerate(self.__specimen.scans) if scan.selected
        ] 

        # get scoring for all selected slides
        self.__scoring = {}
        for i, scan in enumerate(self.__specimen.scans):
            if scan.score is not None:
                self.__scoring[i] = scan.score

        # remove keys from set of requests if they are loaded now
        for key in self.__loaded_images:
            if key in self.__requested:
                self.__requested.remove(key)

        # remove all loaded images from specimens outside the buffer range
        before, after = self.__specimen_buffer
        if self.__selected_indices is not None:
            indices = []
            index_selected_index = self.__selected_indices.index(self.__specimen_index)
            for i in range(-before, after+1):
                index = index_selected_index+i
                if index >= 0 and index < len(self.__selected_indices):
                    indices.append(self.__selected_indices[index])
        else:
            indices = [self.__specimen_index+i for i in range(-before, after+1)]
            indices = [i for i in indices if i >= 0 and i < len(self.__specimens)]
        
        # start to load images and determine background colors
        self.__loaded_images = {
            k: v for (k, v) in self.__loaded_images.items() if k[0] in indices
        }
        self.__background_colors = {
            k: v for (k, v) in self.__background_colors.items() if k[0] in indices
        }

        # load thumbnail images for current specimen if they are not yet loaded   
        for scan_index in range(len(self.__specimen.scans)):
            key = (self.__specimen_index, scan_index, False)
            if key not in self.__loaded_images:
                self._load_thumbail(key)
        
        if self.__multithreading:
            # put keys in the queue for which the workers load the thumbnail images   
            for specimen_index in indices:
                priority = abs(self.__specimen_index-specimen_index)
                for scan_index in range(len(self.__specimens[specimen_index].scans)):
                    # request thumbnail images to be loaded
                    key = (specimen_index, scan_index, False)
                    if key not in self.__loaded_images:
                        if key not in self.__requested:
                            self.__queue.put((priority, key))
                            self.__requested.append(key)
                    # request higher magnification images to be loaded
                    if self.__load_higher_magnification:
                        key = (specimen_index, scan_index, True)
                        if key not in self.__loaded_images:
                            if key not in self.__requested:
                                low_priority = (priority+max(self.__specimen_buffer)+1)
                                self.__queue.put((low_priority, key))
                                self.__requested.append(key)

        # set case and info label
        case = (f'{self.__specimen.pa_number}-{self.__specimen.specimen_numbers}'
            f'  ({self.__specimen_index+1}/{len(self.__specimens)})')
        self.__case_label.setText(case)
        self.__info_label.setText(self.__specimen.description)
        self.__scroll_frame_info.adjustSize()
        self.__textbox.setText(self.__specimen.comments)
        
        # configure scan buttons
        first_visible = None
        first_selected = None
        for i in range(self.__max_buttons):
            # change the button visibility
            if i < len(self.__specimen.scans):
                # get the scan object
                scan = self.__specimen.scans[i]
                # if only H&E slides should be selectable, 
                # hide all buttons for non-H&E stained slides 
                if self.__HE_checkbox.isChecked() and 'IHC' in scan.flags:
                    self.__scan_buttons[i].hide()
                else:
                    # add thumbnail image to button
                    key = (self.__specimen_index, i, False)
                    pixmap = self.__loaded_images[key]
                    button_size = int((1-2*self.__correction_fraction)*self.__button_size)
                    if pixmap is None:
                        self.__scan_buttons[i].background.clear()
                    else:
                        if pixmap.width() > pixmap.height():
                            scaled_pixmap = pixmap.scaledToWidth(button_size)
                        else:
                            scaled_pixmap = pixmap.scaledToHeight(button_size)
                        self.__scan_buttons[i].background.setPixmap(scaled_pixmap)
                    
                    # configure selected button
                    if i in self.__scan_indices:
                        self.__scan_buttons[i].button.setEnabled(True)
                        self.__scan_buttons[i].button.setStyleSheet((
                            'background-color: transparent;'
                            ' border: 5px solid rgb(100,180,100)'
                        ))
                        self.__scan_buttons[i].background.setStyleSheet(
                            f'background-color: rgb{self._get_background_color(key)}'
                        )
                        # change scoring label
                        if i in self.__scoring:
                            self.__scan_buttons[i].score_label.setText(f'{scan.score} ')
                        else:
                            self.__scan_buttons[i].score_label.setText('')
                        if first_selected is None:
                            first_selected = i
                    # configure disabled IHC button
                    elif 'IHC' in scan.flags and not self.__select_non_HE:
                        self.__scan_buttons[i].button.setEnabled(False)
                        self.__scan_buttons[i].button.setStyleSheet((
                            'background-color: transparent;'
                            'border: 1px solid black'
                        ))
                        self.__scan_buttons[i].score_label.setText('')
                        self.__scan_buttons[i].background.setStyleSheet(
                            f'background-color: rgb{self._get_background_color(key)}'
                        )
                    # configure unselected buttons
                    else:
                        self.__scan_buttons[i].button.setEnabled(True)
                        self.__scan_buttons[i].button.setStyleSheet((
                            'background-color: transparent;'
                            ' border: 2px solid black'
                        ))
                        self.__scan_buttons[i].score_label.setText('')
                        self.__scan_buttons[i].background.setStyleSheet(
                            f'background-color: rgb{self._get_background_color(key)}'
                        )

                    # add specimen and staining information
                    if self.__HE_checkbox.isChecked():
                        IHC_count = 0
                        for s in self.__specimen.scans:
                            if scan.slide.specimen_number == s.slide.specimen_number:
                                if scan.slide.block == s.slide.block:
                                    if 'IHC' in s.flags:
                                        IHC_count += 1
                        
                        # construct message
                        message = f'{IHC_count} IHC'
                        if IHC_count != 1:
                            message += 's'
                    else:
                        message = ''

                    self.__scan_buttons[i].IHC_label.setText(message)
                    self.__scan_buttons[i].specimen_label.setText((
                        f' {scan.slide.specimen_number} {scan.slide.block}'
                    ))                    
                    self.__scan_buttons[i].staining_label.setText(
                        f' {scan.slide.staining}'
                    )     

                    # add text to button if no image is available
                    self.__scan_buttons[i].show()
                    if scan.thumbnail_path is None:
                        self.__scan_buttons[i].button.setText('No Thumbnail')
                    else:
                        self.__scan_buttons[i].button.setText('')

                    if first_visible is None:
                        if self.__HE_checkbox.isChecked():
                            if 'HE' in scan.flags:
                                first_visible = i
                        else:
                            first_visible = i                            
            else:
                self.__scan_buttons[i].hide()

        # correct for changing the number of scan buttons visible
        self.__scroll_frame_buttons.adjustSize()

        # initialize the image viewer with the first selected or visible image
        if first_selected is not None:
            self._set_image(first_selected)
        else:
            self._set_image(first_visible)

    def _on_left_click(self):
        """
        Scan button click action to (de)select a particular scan from a specimen.
        """
        # get the scan button index and key
        scan_index = int(self.sender().objectName())
        key = (self.__specimen_index, scan_index, False)

        # change the appearance of the selected button
        if scan_index not in self.__scan_indices:
            # deselect all other selection buttons buttons
            if self.__selection_threshold == 1:
                for i in self.__scan_indices:
                    other_key = (self.__specimen_index, i, False)
                    self.__scan_buttons[i].button.setStyleSheet((
                        'background-color: transparent;'
                        'border: 2px solid black'
                    ))
                    self.__scan_buttons[i].background.setStyleSheet(
                        f'background-color: rgb{self._get_background_color(other_key)}'
                    )
                    if i in self.__scoring:
                        self.__scan_buttons[i].score_label.setText('')
                # reset list and dictionary with selected indices and scores
                self.__scan_indices = []
                self.__scoring = {}

            # select the clicked button if the threshold was not reached
            if len(self.__scan_indices) < self.__selection_threshold:
                self.__scan_indices.append(scan_index)
                self._set_image(scan_index)
                self.__scan_buttons[scan_index].button.setStyleSheet((
                    'background-color: transparent;'
                    'border: 5px solid rgb(100,180,100)'
                ))
                self.__scan_buttons[scan_index].background.setStyleSheet(
                    f'background-color: rgb{self._get_background_color(key)}'
                )
                if self.__score_checkbox.isChecked():
                    score = max([*list(self.__scoring.values()), 0])+1
                    self.__scan_buttons[scan_index].score_label.setText(f'{score} ')
                    self.__scoring[scan_index] = score
        else:
            # deselect the clicked button
            if scan_index in self.__scoring:
                lowest_score = max(list(self.__scoring.values()))
                if self.__scoring[scan_index] != lowest_score:
                    return
                else:
                    self.__scan_buttons[scan_index].score_label.setText('')
                    del self.__scoring[scan_index]
            
            self.__scan_indices.remove(scan_index)
            self._set_image(scan_index)
            self.__scan_buttons[scan_index].button.setStyleSheet((
                'background-color: transparent;'
                'border: 2px solid black'
            ))
            self.__scan_buttons[scan_index].background.setStyleSheet(
                f'background-color: rgb{self._get_background_color(key)}'
            )
    
    def _on_right_click(self):  
        """
        Scan button click action to show a particular scan from a specimen.
        """
        # get the scan button index and key
        scan_index = int(self.sender().objectName())
        self._set_image(scan_index)

    def _next_case(self) -> None:
        """
        Continue to the next case or close the window after the last case.
        """
        self._save_selection()
        # reset selection buttons position
        scroll_bar = self.__scroll_area_buttons.verticalScrollBar()
        scroll_bar.setValue(0)

        # continue to the next specimen or close the window 
        if self.__selected_indices is not None:
            if self.__specimen_index == max(self.__selected_indices):
                self.close()
            else:
                self.__specimen_index = self.__selected_indices[
                    self.__selected_indices.index(self.__specimen_index)+1
                ]
                self._change_widgets()
        elif self.__specimen_index+1 >= len(self.__specimens):
            self.close()
        else:
            self.__specimen_index += 1
            self._change_widgets()

    def _previous_case(self) -> None:
        """
        Return to the previous case.
        """
        self._save_selection()
        # reset selection buttons position
        scroll_bar = self.__scroll_area_buttons.verticalScrollBar()
        scroll_bar.setValue(0)

        # return to the previous specimen
        if self.__selected_indices is not None:
            if self.__specimen_index != min(self.__selected_indices):
                self.__specimen_index = self.__selected_indices[
                    self.__selected_indices.index(self.__specimen_index)-1
                ]
            self._change_widgets()
        elif self.__specimen_index > 0:
            self.__specimen_index -= 1
            self._change_widgets()

    def _store_selection(self) -> None:
        """
        Store selection in specimen instance.
        """
        # store any comments and which scans were selected 
        self.__specimen.comments = self.__textbox.text()
        for scan_index, scan in enumerate(self.__specimen.scans):
            # store selection
            if scan_index in self.__scan_indices:
                scan.selected = True
            else:
                scan.selected = False
                # remove the autoselected flag for scans deselected by the user
                if 'automatically selected' in scan.flags:
                    scan.flags.remove('automatically selected')
            # store scoring
            if scan_index in self.__scoring:
                scan.score = self.__scoring[scan_index]
            else:
                scan.score = None

    def _save_selection(self) -> None:
        """
        Save the selection results.
        """
        # make sure the last information is stored
        self._store_selection()
        # create a new dataframe, add the selection information, and save it
        selection_df = self.__df.copy()
        selection_df['slides'] = [s.information for s in self.__specimens]
        selection_df['selected_scans'] = [s.selected_information for s in self.__specimens]
        selection_df['comments'] = [s.comments for s in self.__specimens]
        selection_df.to_json(self.__output_path)

    def mousePressEvent(self, event):
        """
        Overwritten mouse press event to set focus to main widget.
        """
        self.setFocus()

    def closeEvent(self, a0: QtGui.QCloseEvent):
        """
        Overwritten close event to save selection information.
        """
        self._save_selection()

        # wait for threads to finish
        if self.__multithreading:
            for _ in range(self.__workers):
                self.__queue.put((-1, 'terminate'))

            for t in self.__threads:
                t.join()

        return super().closeEvent(a0)


class SelectionTool:
    """
    Implementation of selection tool class for configuring window and 
    application mainloop.
    """

    def __init__(
        self,
        df: pd.DataFrame, 
        starting_index: Optional[int] = None,
        selected_indices: Optional[list] = None,
        selection_threshold: Optional[int] = None,
        select_by_default: bool = False,
        multithreading: bool = False,
        is_HE_function: Optional[Callable] = None,
        autoselect_function: Optional[Callable] = None,
        output_path: str = 'results.json',
    ) -> None:
        """
        Create the WSI selection window.

        Args:
            df:  Dataframe with specimen information from archive database.
            starting_index:  Starting case for selection (if None, the starting 
                index will be the last case where at least on slide was selected).
            selected_indices:  List with a selection of indices which are shown. 
                The 'previous' and 'next' buttons go to the index smaller and 
                larger in the list, respectively. (if None, all cases are shown).
            selection_threshold:  Maximum number of selectable scans per specimen.
                (None is interpreted as no maximum number).
            select_by_default:  Specifies whether all scans are selected from 
                the start (the selection threshold is overwritten when True).
            multithreading:  Specifies whether higher magnification images are 
                loaded in the background on different threads.
            is_HE_fuction:  Function that returns True when straining name refers 
                to H&E and False otherwise.
            autoselect_function:  Function that returns list with boolean for each
                scan for the input specimen indicating whether it should be 
                automatically selected or not.
            output_path:  Path to output file to save the selection results.
        """
        app = QtWidgets.QApplication(sys.argv)

        # get the screen size
        screen = app.primaryScreen().availableGeometry()
        screen_size = (screen.width(), screen.height())

        # apply stylesheet
        app.setStyleSheet(qdarktheme.load_stylesheet('light'))

        # load fonts
        for font_file in FONTS:
            font_path = os.path.join(os.path.split(fonts.__file__)[0], font_file)
            QtGui.QFontDatabase.addApplicationFont(font_path)

        # create window
        win = SelectionWindow(
            df, 
            screen_size, 
            starting_index,
            selected_indices,
            selection_threshold, 
            select_by_default,
            multithreading,
            is_HE_function,
            autoselect_function,
            output_path,
        )
        win.show()
        sys.exit(app.exec_())