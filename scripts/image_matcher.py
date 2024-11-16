import os
import pickle
import cv2
import numpy as np


class ImageMatcher:
    def __init__(self, base_dir, search_filter=None):
        self.base_dir = base_dir
        self.search_filter = search_filter
        self.hash_size = 8
        self.filters = self.parse_search_filter(search_filter)
        self.hashes = self.load_hashes()

    def parse_search_filter(self, search_filter):
        filters = []
        if search_filter:
            filter_items = [item.strip() for item in search_filter.split(',')]
            for item in filter_items:
                parts = item.strip().split('/')
                if len(parts) == 1:
                    filters.append((parts[0], None))
                elif len(parts) == 2:
                    filters.append((parts[0], parts[1]))
                else:
                    print(f"Warning: Invalid filter item '{item}'. It should be 'slugcat/region' or 'slugcat'.")
        else:
            filters = None  # Include all if no filter is provided
        return filters

    def average_hash(self, image):
        image = cv2.resize(image, (self.hash_size, self.hash_size), interpolation=cv2.INTER_AREA)
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean = image.mean()
        hash_bits = image > mean
        return hash_bits.flatten()

    def hamming_distance(self, hash1, hash2):
        return np.count_nonzero(hash1 != hash2)

    def load_hashes(self):
        hashes = []
        for slugcat in os.listdir(self.base_dir):
            slugcat_path = os.path.join(self.base_dir, slugcat)
            if not os.path.isdir(slugcat_path):
                continue
            if self.filters is not None:
                include_slugcat = any(
                    (f_slugcat == slugcat and f_region is None) for f_slugcat, f_region in self.filters
                )
                include_slugcat_with_region = any(
                    (f_slugcat == slugcat and f_region is not None) for f_slugcat, f_region in self.filters
                )
                if not include_slugcat and not include_slugcat_with_region:
                    continue
            for region in os.listdir(slugcat_path):
                region_path = os.path.join(slugcat_path, region)
                if not os.path.isdir(region_path):
                    continue
                if self.filters is not None:
                    include_region = any(
                        (f_slugcat == slugcat and (f_region == region or f_region is None))
                        for f_slugcat, f_region in self.filters
                    )
                    if not include_region:
                        continue
                hashes_file_path = os.path.join(region_path, 'hashes.pkl')
                if not os.path.isfile(hashes_file_path):
                    continue
                with open(hashes_file_path, 'rb') as f:
                    region_hashes = pickle.load(f)
                    for hash_entry in region_hashes:
                        hash_entry['slugcat'] = slugcat
                        hash_entry['region'] = region
                        hashes.append(hash_entry)
        return hashes

    def match_image(self, image):
        input_hash = self.average_hash(image)
        best_match = None
        best_distance = np.inf
        for hash_entry in self.hashes:
            dataset_hash = hash_entry['hash']
            distance = self.hamming_distance(input_hash, dataset_hash)
            if distance < best_distance:
                best_distance = distance
                best_match = {
                    'slugcat': hash_entry['slugcat'],
                    'region': hash_entry['region'],
                    'filename': hash_entry['filename'],
                    'room_key': hash_entry['room_key'],
                    'room_metadata': hash_entry['room_metadata'],
                    'distance': distance
                }
        return best_match
