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

def get_background_color(
    thumbnail_path: str, 
    channel: int = 2, 
    percentile: float = 87.5,
    default_color: tuple[int] = (255,255,255)
) -> tuple[int]:
    """
    Get the background color for a WSI thumbnail image.
    """
    # return None if the specified path is None or does not exist
    if thumbnail_path is None:
        return default_color
    elif not os.path.exists(thumbnail_path):
        return default_color
        
    # load the image and determine the background color
    image = sitk.GetArrayFromImage(sitk.ReadImage(thumbnail_path))
    image = image.reshape((-1, 3))
    single_channel = image[..., channel]
    mask = np.where(single_channel >= np.percentile(single_channel, percentile), 1, 0)
    color = tuple([round(np.mean(np.extract(mask, image[..., i]))) for i in range(3)])
    
    return color