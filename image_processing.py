import numpy as np
import json
from PIL import Image
import os
import process
import pandas as pd

def get_all_filepaths(input_path):
    images_paths = []
    if input_path[-1] != '/':
        input_path += '/'
    
    items = os.listdir(input_path)
    for item in items:
        extension = item[-3:]
        if extension in ['gif', 'png', 'jpg']:
            images_paths.append(input_path + item)
        else:
            # we assume that item is a directory
            images_paths.extend(get_all_filepaths(input_path + item))
    return images_paths

def change_img_on_background(img, new_background_color):
    background_mask = img[:, :, -1] == 0
    for channel in range(img.shape[-1] - 1):
        img[background_mask, channel] = new_background_color[channel]
    return img 

def process_image(path, background):
    img = Image.open(path)
    img = img.convert('RGBA') # convert to RGBA format
    
    arr = np.array(img, dtype=np.uint8)
    # crop image
    height = arr.shape[0] // 4
    width = arr.shape[1] // 4
    
    box = arr[0: height, 0: width, :]
        
    # standarize background
    if background:
        box = change_img_on_background(box, background)

    return box

class ImageFetcher(process.Process):
    def __init__(self, *args, **kwargs):
        super().__init__(self.process_image, *args, **kwargs)
        
        self.paths = get_all_filepaths(self.input_path) # get all images paths
        self.tasks_waiting.value = len(self.paths)
        self.current_img = 0
        
    def process_image(self, background=(255, 255, 255)): 
        current_path = self.paths[self.current_img]
        img = process_image(current_path, background)
        
        if self.output_path is not None:
            Image.fromarray(img).save(os.path.join(self.output_path,
                                                   str(self.current_img) + '.png'))
        else:
            self.output_buffer.append(img)
        self.current_img += 1
            
    def __repr__(self):
        return '<ImageFetcher with {} tasks>'.format(self.tasks_waiting.value)
    
def get_left_offset(mask):
    offset = -1 # -1 is used where there is no character at all
    for i in range(mask.shape[1]):
        if mask[:, i].any():
            offset = i
            break

    return offset

def get_right_offset(mask):
    offset = -1 # -1 is used where there is no character at all
    for i in range(mask.shape[1]):
        if mask[:, mask.shape[1] - 1 - i].any():
            offset = i
            break

    return offset

def get_top_offset(mask):
    offset = -1 # -1 is used where there is no character at all
    for i in range(mask.shape[0]):
        if mask[i, :].any():
            offset = i
            break

    return offset

def get_bottom_offset(mask):
    offset = -1 # -1 is used where there is no character at all
    for i in range(mask.shape[0]):
        if mask[mask.shape[0] - 1 - i, :].any():
            offset = i
            break

    return offset

def calculate_colors_std(image, mask):
    if image.shape[-1] == 4:
        image = image[..., :-1]
    image = image[mask]
    if image.size:
        return np.std(image, axis=(0,))
    else:
        return [-1, -1, -1]

def calculate_pixels_number(mask):
    return mask.sum(axis=(0, 1))

def calculate_brightness(image, mask):
    if image.shape[-1] == 4: 
        image = image[..., :-1]
    image = image[mask]
    if image.size:
        return np.mean(image)
    else:
        return -1

class ImageStatistics(process.Process):
    
    def __init__(self, stats, *args, **kwargs):
        super().__init__(self.calculate_stats, *args, **kwargs)
        self.stats = stats
        self.task_counter = 0
            
    def calculate_stats(self):
        path = str(self.task_counter) + '.png'
        if self.input_buffer is not None:
            image = self.input_buffer.pop(0)
        else:
            path = os.path.join(self.input_path, path)
            image = np.array(Image.open(path))
        
        mask = image[..., -1] == 255
        colors = ['Red', 'Green', 'Blue']
        d = {}
        
        for stat in self.stats:
            if stat == 'resolution':
                d['ResWidth'] = image.shape[1]
                d['ResHeight'] = image.shape[0]
            elif stat == 'n_pixels':
                d['N_Pixels'] = image.shape[0] * image.shape[1]
            elif stat == 'offset' or stat == 'offsets':
                d['LeftOffset'] = get_left_offset(mask)
                d['RightOffset'] = get_right_offset(mask)
                d['TopOffset'] = get_top_offset(mask)
                d['BottomOffset'] = get_bottom_offset(mask)
            elif stat == 'size' or stat == 'sizes':
                if 'RightOffset' in d:
                    d['Width'] = mask.shape[1] - d['RightOffset'] - d['LeftOffset']
                    d['Height'] = mask.shape[0] - d['TopOffset'] - d['BottomOffset']     
                else:
                    d['Width'] = mask.shape[1] - get_right_offset(mask) - get_left_offset(mask)
                    d['Height'] = mask.shape[0] - get_top_offset(mask) - get_bottom_offset(mask) 
            elif stat == 'bbox' or stat == 'bounding box':
                if 'Width' in d:
                    d['BoundingBoxArea'] = d['Width'] * d['Height']
                else:
                    d['BoundingBoxArea'] = mask.shape[1] - get_right_offset(mask) - get_left_offset(mask) *\
                        mask.shape[0] - get_top_offset(mask) - get_bottom_offset(mask) 
            elif stat == 'character size' or stat == 'char size':
                d['CharacterSize'] = int(calculate_pixels_number(mask))
            elif stat == 'ratio' or stat == 'ratios':
                n_pixels = image.shape[0] * image.shape[1]
                if 'CharacterSize' in d:
                    char_size = d['CharacterSize']
                else:
                    char_size = int(calculate_pixels_number(mask))
                    
                if n_pixels:
                    d['SizeToImageRatio'] = char_size / n_pixels
                else:
                    d['SizeToImageRatio'] = -1
                    
                if 'BoundingBoxArea' in d:
                    if d['BoundingBoxArea']:
                        d['SizeToBoundingBoxRatio'] = char_size / d['BoundingBoxArea']
                    else:
                        d['SizeToBoundingBoxRatio'] = -1
                else:
                    
                    if 'Width' in d:
                        bbox_area = d['Width'] * d['Height']
                    else:
                        bbox_area = mask.shape[1] - get_right_offset(mask) - get_left_offset(mask) *\
                            mask.shape[0] - get_top_offset(mask) - get_bottom_offset(mask) 
                    if bbox_area:
                        d['SizeToBoundingBoxRatio'] = char_size / bbox_area
                    else:
                        d['SizeToBoundingBoxRatio'] = -1   
            elif stat == 'color variety' or stat == 'variety':
                variety = calculate_colors_std(image, mask)
                for i, v in enumerate(variety):
                    d['Variety' + colors[i]] = int(v)
            elif stat == 'brightness':
                d['Brightness'] = calculate_brightness(image, mask)
            else:
                raise AttributeError('Unrecognized statistic:', stat)
        # end for
        if self.output_buffer is not None:
            self.output_buffer.append(d)
        else:
            new_path = os.path.join(self.output_path, str(self.task_counter) + '.json')        
            with open(new_path, 'w') as f:
                d = {'Path': path, 'Statistics': d}
                json.dump(d, f)
        self.task_counter += 1
        
class Logger(process.Process):
    def __init__(self, *args, verbose=False, output_path=None, **kwargs):
        super().__init__(self.log_results, *args, **kwargs)

        columns = ['Path', 'ResWidth', 'N_Pixels', 'ResHeight', 'LeftOffset', 'RightOffset',
                   'TopOffset', 'BottomOffset', 'Width', 'Height', 'BoundingBoxArea',
                   'CharacterSize', 'SizeToImageRatio', 'SizeToBoundingBoxRatio',
                   'VarietyRed', 'VarietyGreen', 'VarietyBlue', 'Brightness']
        self.df = pd.DataFrame(columns=columns)
        self.task_counter = 0
        self.verbose = verbose
        self.output_file = output_path
        
    def log_results(self):
        path = str(self.task_counter) + '.json'
        if self.input_buffer is not None:
            statistics = self.input_buffer.pop(0)
        else:
            path = os.path.join(self.input_path, path)
            with open(path, 'r') as f:
                statistics = json.load(f)['Statistics']
                
        statistics['Path'] = path
        if self.verbose:
            print('Statistics:', statistics)
        
        if self.output_file:
            self.df = self.df.append(statistics, ignore_index=True)
        self.task_counter += 1
   
    def clean(self):
        if self.output_file is not None:
            self.df.set_index('Path', inplace=True)
            self.df.to_csv(self.output_file)
        super().clean()
    
                            