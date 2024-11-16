#!/usr/bin/env python3
import cv2
import argparse
import os
import json
from datetime import timedelta
from image_matcher import ImageMatcher


def parse_arguments():
    parser = argparse.ArgumentParser(description='Process a video and match frames to the dataset.')
    parser.add_argument('video_file', help='Path to the input video file.')
    parser.add_argument('base_dir', help='Base directory containing images.')
    parser.add_argument('--search_filter',
                        help='Comma-separated list of slugcat/region pairs or slugcat names to filter the search.')
    parser.add_argument('--interval', type=float, default=10.0, help='Interval in seconds between frames to process.')
    parser.add_argument('--start_time', type=float, default=0.0, help='Start time in seconds.')
    parser.add_argument('--write_interval', type=int, default=10, help='Write the updated list every x intervals.')
    return parser.parse_args()


def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))


def main():
    args = parse_arguments()
    video_file = args.video_file
    base_dir = args.base_dir
    search_filter = args.search_filter
    interval = args.interval
    start_time = args.start_time
    write_interval = args.write_interval

    matcher = ImageMatcher(base_dir, search_filter)

    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        print(f"Error: Unable to open video file {video_file}")
        return

    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    if frame_rate == 0:
        print("Error: Unable to get frame rate of the video.")
        cap.release()
        return
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / frame_rate

    # Calculate the frame number to start from
    start_frame = int(start_time * frame_rate)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_interval = int(frame_rate * interval)
    current_frame = start_frame

    results = []
    intervals_processed = 0

    json_filename = os.path.splitext(os.path.basename(video_file))[0] + '.json'

    while current_frame < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        if not ret:
            break  # End of video or read error

        best_match = matcher.match_image(frame)
        timestamp = current_frame / frame_rate  # Time in seconds
        formatted_time = format_time(timestamp)

        if best_match:
            result = {
                'timestamp': formatted_time,
                'slugcat': best_match['slugcat'],
                'region': best_match['region'],
                'filename': best_match['filename'],
                'room_key': best_match['room_key'],
                'distance': best_match['distance'],
                'room_metadata': best_match['room_metadata']
            }
            results.append(result)
            print(f"[{formatted_time}] Match found - {best_match['room_key']}")
        else:
            print(f"[{formatted_time}] No match found.")

        current_frame += frame_interval
        intervals_processed += 1

        if intervals_processed % write_interval == 0:
            # Write the updated results to the JSON file
            with open(json_filename, 'w') as f:
                json.dump(results, f, indent=4)
            print(f"Results written to {json_filename}")

    cap.release()

    # Write any remaining results
    with open(json_filename, 'w') as f:
        json.dump(results, f, indent=4)

    print(f"Processing complete. Results saved to {json_filename}")


if __name__ == '__main__':
    main()
