import json
from datetime import timedelta
import argparse
from collections import defaultdict
import os
import markdown


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


def extract_region_from_filename(filename):
    # check if it starts with 'gate_XX_' and if so, ignore the prefix and only use what comes after
    if filename.startswith('gate_'):
        return filename.split('_')[2]
    return filename.split('_')[0]

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
    filename_map = defaultdict(set)
    subregion_counts = {}

    for event in events:
        event_time = parse_timestamp(event['timestamp'])
        # Advance intervals if event_time is beyond the current end_time
        while event_time >= end_time:
            if area_counts:
                # Determine predominant area, slugcat, and top rooms
                predominant_area = max(area_counts, key=area_counts.get)
                predominant_slugcat = max(slugcat_counts, key=slugcat_counts.get)
                top_rooms = sorted(room_counts.items(), key=lambda x: x[1], reverse=True)[:4]
                top_room_names = [room for room, count in top_rooms]
                top_filenames = [
                    {'name': filename, 'path': f"./{predominant_slugcat}/{extract_region_from_filename(filename)}/{filename}"}
                    # get the area from the filename of format "oe_s04_0.png", "sl_b04_2.png" --> "oe", "sl"
                    for room in top_room_names
                    for filename in filename_map[room]
                ]
                top_subregions = sorted(
                    [(subregion, count) for subregion, count in subregion_counts.items() if count > 4],
                    key=lambda x: x[1],
                    reverse=True
                )[:subregion_limit]
                top_subregion_names = [subregion if subregion else 'none' for subregion, count in top_subregions]
                top_subregion_names = [subregion for subregion in top_subregion_names if subregion != 'none']
                summaries.append({
                    'start_time': format_timedelta(start_time),
                    'end_time': format_timedelta(end_time),
                    'slugcat': predominant_slugcat,
                    'region': predominant_area,
                    'rooms': ', '.join(top_room_names),
                    'filenames': top_filenames,
                    'subregions': ', '.join(top_subregion_names)
                })
            start_time = end_time
            end_time = start_time + timedelta(seconds=interval_seconds)
            area_counts = {}
            room_counts = {}
            slugcat_counts = {}
            filename_map = defaultdict(set)
            subregion_counts = {}

        area = event['region']
        area_counts[area] = area_counts.get(area, 0) + 1

        room = event['room_key']
        room_counts[room] = room_counts.get(room, 0) + 1

        slugcat = event['slugcat']
        slugcat_counts[slugcat] = slugcat_counts.get(slugcat, 0) + 1

        filename = event['filename']
        filename_map[room].add(filename)

        subregion = event.get('room_metadata', {}).get('subregion')
        subregion_counts[subregion] = subregion_counts.get(subregion, 0) + 1

    return summaries


def generate_markdown(summaries, video_file, output_file):
    """Generate a markdown file summarizing the player's location data."""
    with open(output_file, 'w') as f:
        f.write("# Location summary\n\n")
        f.write(f"The dataset `{video_file}` contains footage of the following locations:\n\n")

        # Collect all unique slugcat/region pairs
        locations = set()
        for summary in summaries:
            slugcat = summary['slugcat']
            region = summary['region']
            if slugcat and region:
                locations.add(f"[{slugcat}/{region}]({slugcat}/{region})")

        for location in sorted(locations):
            f.write(f"- {location}\n")

        f.write("\n## Details\n\n")
        f.write(
            "| Time              | Slugcat              | Region            | Subregion   | Most frequent rooms                     | Rooms       |\n")
        f.write(
            "|-------------------|----------------------|-------------------|-------------|-----------------------------------------|-------------------|\n")

        for summary in summaries:
            md_filenames = ', '.join(
                [f"[{filename['name']}]({filename['path']})" for filename in summary['filenames']]
            )
            f.write(f"| {summary['start_time']} ")
            f.write(f"| [{summary['slugcat']}]({summary['slugcat']}) ")
            f.write(f"| [{summary['region']}]({summary['slugcat']}/{summary['region']}) ")
            f.write(f"| {summary['subregions']} ")
            f.write(f"| {summary['rooms']} ")
            f.write(f"| {md_filenames} |\n")

        print(f"Markdown file saved to {output_file}")


def generate_html(summaries, video_file, output_file):
    """Generate an HTML file summarizing the player's location data."""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Location Summary</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                max-width: 100%;
                padding: 20px;
                margin: auto;
                background: #fff;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
            }}
            .preview img {{
                max-width: 100px;
                max-height: 100px;
                margin-right: 5px;
            }}
            .preview {{
                white-space: nowrap;
            }}
            .preview.large img {{
                max-width: 175px;
                max-height: 175px;
            }}
            .preview.xlarge img {{
                max-width: 250px;
                max-height: 250px;
            }}
            button {{
                padding: 3px 10px;
                background-color: #3498db;
                border-radius: 5px;
                color: #fff;
                border: none;
                cursor: pointer;
            }}
        </style>
        <script>
            function togglePreviewSize() {{
                const previews = document.querySelectorAll('.preview');
                previews.forEach(preview => {{
                    if (preview.classList.contains('large')) {{
                        preview.classList.remove('large');
                        preview.classList.add('xlarge');
                    }} else if (preview.classList.contains('xlarge')) {{
                        preview.classList.remove('xlarge');
                    }} else {{
                        preview.classList.add('large');
                    }}
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Location Summary</h1>
            <p>The dataset <strong>{video_file}</strong> contains footage of the following locations:</p>
            <ul>
    """
    # Collect all unique slugcat/region pairs
    locations = set()
    for summary in summaries:
        slugcat = summary['slugcat']
        region = summary['region']
        if slugcat and region:
            locations.add(f"<li><a href='{slugcat}/{region}'>{slugcat}/{region}</a></li>")
    html_content += "\n".join(sorted(locations))
    html_content += """
            </ul>
            <h2>Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Slugcat</th>
                        <th>Region</th>
                        <th>Subregion</th>
                        <th>Most Frequent Rooms</th>
                        <th>Preview <button style="margin-left:5px" onclick="togglePreviewSize()">Resize</button></th>
                        <th>Rooms</th>
                    </tr>
                </thead>
                <tbody>
    """
    for summary in summaries:
        html_filenames = ', '.join(
            [f"<a href='{filename['path']}'>{filename['name']}</a>" for filename in summary['filenames']]
        )
        preview_images = ''.join(
            f"<img src='{filename['path']}' alt='{filename['name']}'>" for filename in summary['filenames'][:3]
        )
        html_content += f"""
                    <tr>
                        <td>{summary['start_time']}</td>
                        <td><a href="{summary['slugcat']}">{summary['slugcat']}</a></td>
                        <td><a href="{summary['slugcat']}/{summary['region']}">{summary['region']}</a></td>
                        <td>{summary['subregions']}</td>
                        <td>{summary['rooms']}</td>
                        <td class="preview">{preview_images}</td>
                        <td>{html_filenames}</td>
                    </tr>
        """
    html_content += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    with open(output_file.replace('.md', '.html'), 'w') as f:
        f.write(html_content)
    print(f"HTML file saved to {output_file.replace('.md', '.html')}")


def main():
    parser = argparse.ArgumentParser(description='Generate a markdown summary for player locations.')
    parser.add_argument('json_file', help='Path to the input JSON file.')
    parser.add_argument('--format', choices=['md', 'html'], default='md', help='Output format: markdown or HTML.')
    parser.add_argument('-o', '--output_file', default='<json_filename>', help='Output markdown/HTML file name.')
    parser.add_argument('-i', '--interval', type=int, default=5, help='Interval duration in minutes.')
    parser.add_argument('-s', '--subregion_limit', type=int, default=10,
                        help='Maximum number of subregions to include.')
    args = parser.parse_args()

    if args.output_file == '<json_filename>':
        args.output_file = os.path.splitext(args.json_file)[0] + ('.md' if args.format == 'md' else '.html')
    # append correct filename if not provided
    if (not args.output_file.endswith('.md') and args.format == 'md') or (
            not args.output_file.endswith('.html') and args.format == 'html'):
        args.output_file += '.md' if args.format == 'md' else '.html'

    with open(args.json_file, 'r') as f:
        events = json.load(f)

    summaries = summarize_locations(events, interval_minutes=args.interval, subregion_limit=args.subregion_limit)

    if args.format == 'md':
        generate_markdown(summaries, os.path.splitext(args.json_file)[0], args.output_file)
    else:
        generate_html(summaries, os.path.splitext(args.json_file)[0], args.output_file)


if __name__ == '__main__':
    main()
