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
Utility classes for specimen and slide information.
"""

import re
from pathlib import Path
from natsort import natsorted
from ._general_utils import is_HE


class Specimen:
    """
    Implementation of specimen class for interacting with metadata.
    """

    def __init__(self, specimen_information: str, description: str = '') -> None:
        """
        Initialize specimen instance and corresponding slide and scan instances.

        Args:
            specimen_information: metadata from all slides.
            description: text description of the specimen.
        """
        # convert specimen information from a string to a dictionary if necessary
        if isinstance(specimen_information, str):
            specimen_information = eval(specimen_information)
        
        # create slide instances and initialize attributes
        self.__slides = [Slide(self, info) for info in specimen_information['slides']]
        self.__scans = []
        for slide in self.__slides:
            self.__scans.extend(slide.scans)
        self.__description = description

        # check if the pa_number matches for all slides
        pa_numbers = set([slide.pa_number for slide in self.__slides])
        if len(pa_numbers) == 0:
            self.__pa_number = None
        elif len(pa_numbers) == 1:
            self.__pa_number = pa_numbers.pop()
        else:
            raise AssertionError(('At least two slides with a different '
                'pa_number were assigned to this specimen.'))

        # find all specimen numbers
        specimen_numbers = list(set([slide.specimen_number for slide in self.slides]))
        specimen_numbers = ["''" if s == '' else s for s in specimen_numbers]
        self.__specimen_numbers = ', '.join(natsorted(specimen_numbers))

        # initialize additional instance attributes for comments
        if 'comments' in specimen_information:
            self.comments = specimen_information['comments']
        else:
            self.comments = '' 

    def sort_slides(self, is_HE = is_HE):
        """
        Sort slides based on specimen number, block number, and staining.
        """
        # create list with tuples that contain the characteristics for sorting
        # in decending order of importance, with the slide index as last element
        unsorted_slides = []
        for i, s in enumerate(self.__slides):
            unsorted_slides.append(
                (s.specimen_number, s.block, not is_HE(s.staining), s.staining, i),
            )
        # sort the items in the list
        indices_sorted_slides = [s[-1] for s in natsorted(unsorted_slides)]
        
        # apply the new order to the slides and scans
        self.__slides = [self.__slides[i] for i in indices_sorted_slides]
        self.__scans = []
        for slide in self.__slides:
            self.__scans.extend(slide.scans)

    @property
    def information(self):
        return {
            'slides': [slide.information for slide in self.__slides], 
            'comments': self.comments,
        }

    @property
    def selected_information(self):
        # get the information of the selected scans
        slide_information = []
        for slide in self.__slides:
            if slide.selected_information is not None:
                slide_information.append(slide.selected_information)
        # return information if at least one scan as selected
        if len(slide_information):
            return {
                'slides': slide_information, 
                'comments': self.comments,
            }
        else:
            return None

    @property
    def slides(self):
        return self.__slides
    
    @property
    def scans(self):
        return self.__scans

    @property
    def pa_number(self):
        return self.__pa_number

    @property
    def specimen_numbers(self):
        return self.__specimen_numbers

    @property
    def description(self):
        return self.__description

    def __repr__(self) -> str:
        description = str([s for s in self.slides])
        return f'Specimen {self.pa_number}-{self.specimen_numbers}: {description}'


class Slide:
    """
    Implementation of slide class for interacting with metadata.
    """

    def __init__(self, specimen: Specimen, slide_information: dict) -> None:
        """
        Initialize slide instance.

        Args:
            slide_information: slide metadata.
        """
        # initialize instance attributes for slide and create scan instances
        self.__specimen = specimen
        self.__slide_information = {
            key: val for (key, val) in slide_information.items() if key != 'scan'
        }
        self.__scans = [Scan(self, info) for info in slide_information['scan']]        

    @property
    def specimen(self):
        return self.__specimen
    
    @property
    def information(self):
        return {
            **self.__slide_information,
            'scan': [scan.information for scan in self.__scans],
        }

    @property
    def selected_information(self):
        # get the information for each selected scan
        scan_information = [
            scan.information for scan in self.__scans if scan.selected
        ]
        # return information if at least one scan was selected
        if len(scan_information):
            return {
                **self.__slide_information,
                'scan': scan_information,
            }
        else:
            return None

    @property
    def scans(self):
        return self.__scans

    @property
    def pa_number(self):
        return self.__slide_information['pa_number']
    
    @property
    def specimen_number(self):
        return self.__slide_information['specimen_nr']

    @property
    def block(self):
        return self.__slide_information['block']
    
    @property
    def staining(self):
        return self.__slide_information['staining']

    def __repr__(self) -> str:
        return f'Slide(Block {self.block}, {self.staining}, {len(self.scans)} scan(s))'


class Scan:
    """
    Implementation of scan class for interacting with metadata.
    """

    def __init__(self, slide: Slide, scan_information: dict) -> None:
        """
        Initialize scan instance.

        Args:
            scan_information: scan metadata.
        """
        # initialize instance attributes for scan
        self.__slide = slide
        self.__scan_information = scan_information  
        
        base_dir = self.__scan_information['base_dir']
        files = sorted(self.__scan_information['files']['SLIDE'])
        self.__paths = [
            str(Path(*re.split('\\/', base_dir), file)) for file in files
        ]
        
        # account for thumbnail image not being available
        if 'THUMBNAIL' in self.__scan_information['files']:
            if len(self.__scan_information['files']['THUMBNAIL']): 
                thumb_file = self.__scan_information['files']['THUMBNAIL'][0]
                self.__thumb_path = str(Path(*re.split('\\/', base_dir), thumb_file))
            else:
                self.__thumb_path = None
        else:
            self.__thumb_path = None
        
        # initialize additional instance attributes for states
        if 'selected' in scan_information:
            self.selected = self.__scan_information['selected']
        else:
            self.selected = None

        if 'flags' in scan_information:
            self.flags = self.__scan_information['flags']
        else:
            self.flags = []    

    @property
    def slide(self):
        return self.__slide
    
    @property
    def information(self):
        self.__scan_information['selected'] = self.selected
        self.__scan_information['flags'] = self.flags
        return self.__scan_information

    @property
    def paths(self):
        return self.__paths

    @property
    def thumbnail_path(self):
        return self.__thumb_path

    def __repr__(self) -> str:
        return f'Scan object'