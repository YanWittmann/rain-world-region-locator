#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import shutil


def parse_arguments():
    parser = argparse.ArgumentParser(description="Automate the Rain World Region Locator process.")
    parser.add_argument('video_file', help='Path to the input video file.')
    parser.add_argument('--search_filter', help='Comma-separated list of slugcat/region pairs or slugcat names.')
    parser.add_argument('--start_time', type=int, default=0, help='Start time in seconds. Default is 0.')
    parser.add_argument('--interval', type=int, default=10, help='Frame processing interval in seconds. Default is 10.')
    parser.add_argument('--transcript_file', help='Path to the video transcript CSV file.')
    parser.add_argument('--model', default='mannix/llama3.1-8b-abliterated:latest',
                        help='Model name for summarization.')
    parser.add_argument('--base_url', default='http://localhost:11434', help='Base URL for the language model API.')
    parser.add_argument('--output_dir', help='Directory to save the outputs. Defaults to the video file directory.')
    parser.add_argument('--screenshots_dir', help='Path to the Rain World screenshots directory.')
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Validate video file
    if not os.path.isfile(args.video_file):
        print(f"Error: Video file '{args.video_file}' does not exist.")
        sys.exit(1)

    # Infer output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.dirname(os.path.abspath(args.video_file))

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Infer base directory for screenshots
    if args.screenshots_dir:
        screenshots_base_dir = args.screenshots_dir
    else:
        # Default Steam installation path (modify if different)
        screenshots_base_dir = os.path.expandvars(
            r'I:\SteamLibrary\steamapps\common\Rain World\MapExport\Input'
        )
        if not os.path.isdir(screenshots_base_dir):
            print("Error: Could not find the Rain World screenshots directory.")
            sys.exit(1)

    # Infer search filter
    search_filter = args.search_filter if args.search_filter else ''

    # Generate base filenames
    video_filename = os.path.basename(args.video_file)
    base_name, _ = os.path.splitext(video_filename)
    json_file = os.path.join(output_dir, f"{base_name}.json")
    html_file = os.path.join(screenshots_base_dir, f"{base_name}.html")

    # Process the video
    print("Processing video...")
    process_video_cmd = [
        sys.executable, 'process_video.py',
        args.video_file,
        screenshots_base_dir,
        '--search_filter', search_filter,
        '--start_time', str(args.start_time),
        '--interval', str(args.interval)
    ]
    print(' '.join(process_video_cmd))
    subprocess.run(process_video_cmd, check=True)

    # Summarize the transcript if provided
    if args.transcript_file:
        print("Summarizing video transcript...")
        summary_json = os.path.join(output_dir, f"{base_name}-summary.json")
        transcript_summarizer_cmd = [
            sys.executable, 'transcript_summarizer.py',
            args.transcript_file,
            '--output_file', summary_json,
            '--base_url', args.base_url,
            '--model', args.model
        ]
        print(' '.join(transcript_summarizer_cmd))
        subprocess.run(transcript_summarizer_cmd, check=True)

    # Generate the HTML overview table
    print("Generating HTML overview table...")
    interpret_cmd = [
        sys.executable, 'interpret_overview_table.py',
        json_file,
        '--format', 'html',
        '--output_file', html_file
    ]
    if args.transcript_file:
        interpret_cmd.extend(['--transcript_file', summary_json])

    print(' '.join(interpret_cmd))
    subprocess.run(interpret_cmd, check=True)

    print(f"HTML overview table generated at: {html_file}")


if __name__ == '__main__':
    main()
