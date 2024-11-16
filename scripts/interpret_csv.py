import json
import os
from datetime import timedelta
import pandas as pd
import argparse

def load_data(json_file):
    """Load event data from a JSON file."""
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def parse_timestamp(timestamp_str):
    """Parse a timestamp string in 'hh:mm:ss' format into a timedelta object."""
    h, m, s = map(int, timestamp_str.split(':'))
    return timedelta(hours=h, minutes=m, seconds=s)

def format_timedelta(td):
    """Format a timedelta object as 'hh:mm:ss'."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02}:{seconds:02}"

def summarize_locations(events, interval_minutes=5, subregion_limit=10):
    """Summarize player's predominant location and rooms for each interval."""
    summaries = []
    interval_seconds = interval_minutes * 60
    events.sort(key=lambda x: parse_timestamp(x['timestamp']))

    if not events:
        return summaries

    start_time = parse_timestamp(events[0]['timestamp'])
    end_time = start_time + timedelta(seconds=interval_seconds)
    area_counts = {}
    room_counts = {}
    slugcat_counts = {}
    filename_map = {}
    subregion_counts = {}

    for event in events:
        event_time = parse_timestamp(event['timestamp'])
        # Advance intervals if event_time is beyond the current end_time
        while event_time >= end_time:
            if area_counts:
                # Determine predominant area, slugcat, and top rooms
                predominant_area = max(area_counts, key=area_counts.get)
                predominant_slugcat = max(slugcat_counts, key=slugcat_counts.get)
                # Get top rooms
                top_rooms = sorted(room_counts.items(), key=lambda x: x[1], reverse=True)[:4]
                top_room_names = [room for room, count in top_rooms]
                # Get filenames for top rooms
                top_filenames = [', '.join(filename_map[room]) for room in top_room_names]
                # Get top subregions
                top_subregions = sorted(
                    [(subregion, count) for subregion, count in subregion_counts.items() if count > 4],
                    key=lambda x: x[1],
                    reverse=True
                )[:subregion_limit]
                top_subregion_names = [subregion if subregion else 'Unknown' for subregion, count in top_subregions]
                summaries.append({
                    'start_time': format_timedelta(start_time),
                    'end_time': format_timedelta(end_time),
                    'slugcat': predominant_slugcat,
                    'area': predominant_area,
                    'rooms': ', '.join(top_room_names),
                    'filenames': '; '.join(top_filenames),
                    'subregions': ', '.join(top_subregion_names)
                })
            else:
                # No events in this interval
                summaries.append({
                    'start_time': format_timedelta(start_time),
                    'end_time': format_timedelta(end_time),
                    'slugcat': None,
                    'area': None,
                    'rooms': None,
                    'filenames': None,
                    'subregions': None
                })
            # Move to the next interval
            start_time = end_time
            end_time = start_time + timedelta(seconds=interval_seconds)
            area_counts = {}
            room_counts = {}
            slugcat_counts = {}
            filename_map = {}
            subregion_counts = {}
        # Count the area, room, slugcat occurrence in the current interval
        area = event['region']
        area_counts[area] = area_counts.get(area, 0) + 1

        room = event['room_key']
        room_counts[room] = room_counts.get(room, 0) + 1

        slugcat = event['slugcat']
        slugcat_counts[slugcat] = slugcat_counts.get(slugcat, 0) + 1

        filename = event['filename']
        if room not in filename_map:
            filename_map[room] = set()
        filename_map[room].add(filename)

        # Get subregion from room metadata
        subregion = event.get('room_metadata', {}).get('subregion')
        subregion_counts[subregion] = subregion_counts.get(subregion, 0) + 1

    # Handle the last interval after processing all events
    if area_counts:
        predominant_area = max(area_counts, key=area_counts.get)
        predominant_slugcat = max(slugcat_counts, key=slugcat_counts.get)
        top_rooms = sorted(room_counts.items(), key=lambda x: x[1], reverse=True)[:4]
        top_room_names = [room for room, count in top_rooms]
        top_filenames = [', '.join(filename_map[room]) for room in top_room_names]
        top_subregions = sorted(subregion_counts.items(), key=lambda x: x[1], reverse=True)[:subregion_limit]
        top_subregion_names = [subregion if subregion else 'Unknown' for subregion, count in top_subregions]
        summaries.append({
            'start_time': format_timedelta(start_time),
            'end_time': format_timedelta(end_time),
            'slugcat': predominant_slugcat,
            'area': predominant_area,
            'rooms': ', '.join(top_room_names),
            'filenames': '; '.join(top_filenames),
            'subregions': ', '.join(top_subregion_names)
        })
    else:
        # No events in the last interval
        summaries.append({
            'start_time': format_timedelta(start_time),
            'end_time': format_timedelta(end_time),
            'slugcat': None,
            'area': None,
            'rooms': None,
            'filenames': None,
            'subregions': None
        })

    return summaries

def save_summaries_to_csv(summaries, output_file):
    """Save the summaries to a CSV file."""
    # Convert summaries to DataFrame
    df = pd.DataFrame(summaries)
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Summaries saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Summarize player locations.')
    parser.add_argument('json_file', help='Path to the input JSON file.')
    parser.add_argument('-o', '--output_file', default='<json_filename>.csv', help='Output CSV file name.')
    parser.add_argument('-i', '--interval', type=int, default=5, help='Interval duration in minutes.')
    parser.add_argument('-s', '--subregion_limit', type=int, default=10, help='Maximum number of subregions to include.')
    args = parser.parse_args()

    if args.output_file == '<json_filename>.csv':
        args.output_file = os.path.splitext(args.json_file)[0] + '.csv'

    events = load_data(args.json_file)
    summaries = summarize_locations(events, interval_minutes=args.interval, subregion_limit=args.subregion_limit)
    save_summaries_to_csv(summaries, args.output_file)

if __name__ == '__main__':
    main()
