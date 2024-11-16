import cv2
import argparse
from image_matcher import ImageMatcher


def parse_arguments():
    parser = argparse.ArgumentParser(description='Match an image to the dataset using image hashing.')
    parser.add_argument('image_file', help='Path to the input image file.')
    parser.add_argument('base_dir', help='Base directory containing images.')
    parser.add_argument('--search_filter',
                        help='Comma-separated list of slugcat/region pairs or slugcat names to filter the search.')
    return parser.parse_args()


def main():
    args = parse_arguments()
    image_file = args.image_file
    base_dir = args.base_dir
    search_filter = args.search_filter

    image = cv2.imread(image_file)
    if image is None:
        print(f"Error: Unable to read image {image_file}")
        return

    matcher = ImageMatcher(base_dir, search_filter)
    best_match = matcher.match_image(image)

    if best_match:
        print("Best match found:")
        print(f"Slugcat: {best_match['slugcat']}")
        print(f"Region: {best_match['region']}")
        print(f"Filename: {best_match['filename']}")
        print(f"Room Key: {best_match['room_key']}")
        print(f"Hamming Distance: {best_match['distance']}")
        print("Room Metadata:")
        for key, value in best_match['room_metadata'].items():
            if key not in ['tiles', 'nodes']:
                print(f"  {key}: {value}")
    else:
        print("No matches found.")


if __name__ == '__main__':
    main()
