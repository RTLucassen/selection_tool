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
General utility functions for selection tool.
"""

import os
import numpy as np
import SimpleITK as sitk
import matplotlib.pyplot as plt

def is_HE(staining: str) -> bool:
    return True if 'he' in staining.lower() else False

def calculate_window_geometry(
    screen_size: tuple[int], 
    fraction: float,
) -> tuple[int]:
    """
    Calculate the width, height, and top left position of the window
    based on the screen size and the faction of the height and width 
    to be occupied by the window.

    Args:
        screen_size: size of computer screen as (width, height).
        fraction: fraction of height and width occupied by selection window.

    Returns:
        window_geometry: width, height, and top left position of the window.
    """
    width = screen_size[0]*fraction
    height = screen_size[1]*fraction
    horizontal_offset = (screen_size[0]-width)/2
    vertical_offset = (screen_size[1]-height)/2

    return (int(horizontal_offset), int(vertical_offset), int(width), int(height))

def number2roman(number: str) -> str:
    """
    Convert number to roman numeral.
    """
    try:
        number = int(number)
    except:
        return number
    else:
        # define number map
        number_map = [
            (1000, 'M'), 
            (900, 'CM'), 
            (500, 'D'), 
            (400, 'CD'), 
            (100, 'C'), 
            (90, 'XC'), 
            (50, 'L'), 
            (40, 'XL'), 
            (10, 'X'), 
            (9, 'IX'), 
            (5, 'V'), 
            (4, 'IV'), 
            (1, 'I'),
        ]

        # define starting string
        roman = ''
        while number > 0:
            for i, r in number_map:
                while number >= i:
                    roman += r
                    number -= i

        return roman
