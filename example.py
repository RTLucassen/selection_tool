"""
Creates example dataset to test the selection tool.

Steps:
1) Four whole slide images are downloaded from the GDC data portal (~2.2GB).
2) Low magnification thumbnail images are created for each slide.
3) The selection tool is started using the example dataset that was created.
"""

import os
import requests

import pandas as pd
import SimpleITK as sitk
from slideloader import SlideLoader
from tqdm import tqdm

from selection_tool import SelectionTool

# specify the directory where the example folder should be configured
directory = ''

# ------------------------------------------------------------------------------

# create example folder
example_directory = os.path.join(directory, 'selection_tool_example')
if not os.path.exists(example_directory):
    os.mkdir(example_directory)

# define a dictionary with file ids and names to download from GDC data portal
data_endpoint = "https://api.gdc.cancer.gov/data/"
files = {
    '2369c69b-2065-4913-bfd9-5d7b0506c1e7': 
        'TCGA-FS-A1ZU-06Z-00-DX3.0C477EE6-C085-42BE-8BAD-E3D6935ABE48.svs',
    '9834e70e-91dc-47f6-b814-4cff90b13a25': 
        'TCGA-FS-A1ZU-06Z-00-DX1.3AF5FEC8-DD45-4B7E-B580-20C0F73AC4BB.svs',
    'f3a53d50-c9aa-47cc-8cc8-0f933f7eb105': 
        'TCGA-EB-A44O-01Z-00-DX1.A07646AF-D30D-4C44-B8F6-B81D3F2A4F5D.svs',
    'b3f22fc1-f70c-4474-9bed-34fbf83c13bc': 
        'TCGA-EB-A44O-06Z-00-DX1.788C33F2-3766-4792-B8DF-52C5F3E8AEDB.svs',
}

# NOTE: The patient information is from TCGA. The pa, specimen, and block numbers 
# were made up to illustrate how the selection tool works.

# define input dataframe  
description = [
    ('Case ID:\tTCGA-FS-A1ZU\n'
    'Patient details: Female, 70 years old.\n'
    'Primary diagnosis: Malignant melanoma.'),
    ('Case ID:\tTCGA-EB-A44O\n'
    'Patient details: Male, 69 years old.\n'
    'Primary diagnosis: Malignant melanoma.'),
]
slides = [{
    'slides': [{
        'pa_number': 'T23-12345', 
        'specimen_nr': 'I', 
        'block': '1', 
        'staining': 'H&E', 
        'scan': [{
            'base_dir': example_directory, 
            'files': {
                'THUMBNAIL': [
                    'TCGA-FS-A1ZU-06Z-00-DX3.0C477EE6-C085-42BE-8BAD-E3D6935ABE48.png',
                ],
                'SLIDE': [
                    'TCGA-FS-A1ZU-06Z-00-DX3.0C477EE6-C085-42BE-8BAD-E3D6935ABE48.svs',
                ],
            }
        }],
    },
    {
       'pa_number': 'T23-12345', 
        'specimen_nr': 'I', 
        'block': '2', 
        'staining': 'H&E', 
        'scan': [{
            'base_dir': example_directory, 
            'files': {
                'THUMBNAIL': [
                    'TCGA-FS-A1ZU-06Z-00-DX1.3AF5FEC8-DD45-4B7E-B580-20C0F73AC4BB.png',
                ],
                'SLIDE': [
                    'TCGA-FS-A1ZU-06Z-00-DX1.3AF5FEC8-DD45-4B7E-B580-20C0F73AC4BB.svs',
                ],
            }
        }],
    }],
},
{
        'slides': [{
        'pa_number': 'T23-50001', 
        'specimen_nr': 'I', 
        'block': '1', 
        'staining': 'H&E', 
        'scan': [{
            'base_dir': example_directory, 
            'files': {
                'THUMBNAIL': [
                    'TCGA-EB-A44O-01Z-00-DX1.A07646AF-D30D-4C44-B8F6-B81D3F2A4F5D.png',
                ],
                'SLIDE': [
                    'TCGA-EB-A44O-01Z-00-DX1.A07646AF-D30D-4C44-B8F6-B81D3F2A4F5D.svs',
                ],
            }
        }],
    },
    {
       'pa_number': 'T23-50001', 
        'specimen_nr': 'II', 
        'block': '1', 
        'staining': 'H&E', 
        'scan': [{
            'base_dir': example_directory, 
            'files': {
                'THUMBNAIL': [
                    'TCGA-EB-A44O-06Z-00-DX1.788C33F2-3766-4792-B8DF-52C5F3E8AEDB.png',
                ],
                'SLIDE': [
                    'TCGA-EB-A44O-06Z-00-DX1.788C33F2-3766-4792-B8DF-52C5F3E8AEDB.svs',
                ],
            }
        }],
    }],
}]
df = pd.DataFrame.from_dict({'description': description, 'slides': slides})

# download example WSIs (if necessary)
for file_id, filename in files.items():
    if not os.path.exists(os.path.join(example_directory, filename)):
        # create request
        response = requests.get(
            data_endpoint+file_id, 
            stream=True,
        )
        # configure progress bar
        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024
        print(f'Start downloading {filename} ({total_size_in_bytes/1e6:0.0F} MB)')
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
        
        # start downloading data
        path = os.path.join(example_directory, filename)
        with open(path, "wb") as output_file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                output_file.write(data)
        progress_bar.close()

        # check if the file was downloaded correctly
        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            raise IOError('The file was not successfully downloaded')

# create thumbnail images for WSIs (if necessary)
loader = SlideLoader()
for file_id, filename in files.items():
    slide_path = os.path.join(example_directory, filename)
    thumbnail_path = slide_path.replace('.svs', '.png')
    if not os.path.exists(thumbnail_path):        
        # create low resolution thumbnails
        loader.load_slide(slide_path)
        magnification = min(loader.get_properties()['magnification_levels'])
        thumbnail_image = loader.get_image(magnification)[None, ...]
        sitk.WriteImage(sitk.GetImageFromArray(thumbnail_image), thumbnail_path)

SelectionTool(
    df=df, 
    starting_index=None,
    selected_indices=None,
    selection_threshold=None,
    multithreading=True,
    select_by_default=False,
    output_path=os.path.join(example_directory, 'selection_results.json'),
)

