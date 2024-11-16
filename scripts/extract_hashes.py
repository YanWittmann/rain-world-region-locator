import os
import cv2
import argparse
import pickle
import json


def parse_arguments():
    parser = argparse.ArgumentParser(description='Extract image hashes and metadata from images.')
    parser.add_argument('base_dir', help='Base directory containing images.')
    parser.add_argument('--search_filter',
                        help='Comma-separated list of slugcat/region pairs or slugcat names to filter the extraction.')
    return parser.parse_args()


def is_image_file(filename):
    return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff'))


def average_hash(image, hash_size=8):
    # Convert image to grayscale and resize
    image = cv2.resize(image, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    # Convert to grayscale
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Compute the mean
    mean = image.mean()
    # Create hash based on mean
    hash_bits = image > mean
    return hash_bits.flatten()


def main():
    args = parse_arguments()
    base_dir = args.base_dir
    search_filter = args.search_filter

    # Parse search_filter into a list of (slugcat, region) tuples
    filters = []
    if search_filter:
        filter_items = [item.strip() for item in search_filter.split(',')]
        for item in filter_items:
            parts = item.strip().split('/')
            if len(parts) == 1:
                # Only slugcat specified
                filters.append((parts[0], None))
            elif len(parts) == 2:
                # Slugcat and region specified
                filters.append((parts[0], parts[1]))
            else:
                print(
                    f"Warning: Invalid filter item '{item}'. It should be in the format 'slugcat/region' or 'slugcat'.")

    for slugcat in os.listdir(base_dir):
        slugcat_path = os.path.join(base_dir, slugcat)
        if not os.path.isdir(slugcat_path):
            continue

        # If filters are specified, check if this slugcat should be included
        if filters:
            include_slugcat = any(
                (f_slugcat == slugcat and f_region is None) for f_slugcat, f_region in filters
            )
            include_slugcat_with_region = any(
                (f_slugcat == slugcat and f_region is not None) for f_slugcat, f_region in filters
            )
            if not include_slugcat and not include_slugcat_with_region:
                continue

        for region in os.listdir(slugcat_path):
            region_path = os.path.join(slugcat_path, region)
            if not os.path.isdir(region_path):
                continue

            # If filters are specified, check if this slugcat/region should be included
            if filters:
                include_region = any(
                    (f_slugcat == slugcat and f_region == region) or
                    (f_slugcat == slugcat and f_region is None)
                    for f_slugcat, f_region in filters
                )
                if not include_region:
                    continue

            print(f"Processing region: {slugcat}/{region}")
            hashes = []

            # Read metadata.json
            metadata_path = os.path.join(region_path, 'metadata.json')
            if not os.path.isfile(metadata_path):
                print(f"Warning: metadata.json not found in {region_path}")
                continue

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            rooms = metadata.get('rooms', {})
            if not rooms:
                print(f"Warning: No rooms found in metadata.json in {region_path}")
                continue

            # Prepare room keys for matching
            room_keys = {room_key.lower(): room_data for room_key, room_data in rooms.items()}

            # Process images in region directory
            for filename in os.listdir(region_path):
                if is_image_file(filename):
                    image_path = os.path.join(region_path, filename)
                    base_filename = os.path.splitext(filename)[0]

                    # Find matching room
                    matched_room_key = None
                    matched_room_data = None

                    for room_key_lower, room_data in room_keys.items():
                        room_key_original = room_data['name']  # Original case
                        if (base_filename.lower() == room_key_lower) or \
                                (base_filename.lower().startswith(room_key_lower + '_')):
                            matched_room_key = room_key_original
                            matched_room_data = room_data
                            break

                    if not matched_room_key:
                        # Image does not correspond to any room
                        continue

                    # Read image
                    image = cv2.imread(image_path)
                    if image is None:
                        print(f"Warning: Unable to read image {image_path}")
                        continue

                    # Compute average hash
                    hash_value = average_hash(image)

                    # Remove 'tiles' and 'nodes' from room metadata if present
                    matched_room_data.pop('tiles', None)
                    matched_room_data.pop('nodes', None)

                    # Store hash and metadata
                    hash_entry = {
                        'filename': filename,
                        'hash': hash_value,
                        'room_key': matched_room_key,
                        'room_metadata': matched_room_data
                    }
                    hashes.append(hash_entry)

            # Save hashes to a pickle file in the region directory
            hashes_file_path = os.path.join(region_path, 'hashes.pkl')
            with open(hashes_file_path, 'wb') as f:
                pickle.dump(hashes, f)

            print(f"Hash extraction complete for [{slugcat}/{region}]: {hashes_file_path}")


if __name__ == '__main__':
    main()
