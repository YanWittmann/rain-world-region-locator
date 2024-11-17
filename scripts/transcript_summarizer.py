import argparse
import json
import re
from datetime import timedelta
import concurrent.futures
from threading import Lock
from typing import List, Dict
from CompletionClient import CompletionClient


def parse_transcript(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()

    entries = []
    for line in lines:
        match = re.match(r"(\d+:\d+),([\d.]+),([\d.]+),(.*)", line)
        if match:
            timestamp, _, _, text = match.groups()
            minutes, seconds = map(int, timestamp.split(":"))
            total_seconds = minutes * 60 + seconds
            entries.append(
                {"timestamp": total_seconds,
                 "text": text.strip()}
            )
    return entries


def batch_transcript(entries, batch_size=300):
    batches = []
    current_batch = {"start": entries[0]["timestamp"], "end": None, "text": ""}
    for entry in entries:
        if entry["timestamp"] - current_batch["start"] > batch_size:
            current_batch["end"] = entry["timestamp"]
            batches.append(current_batch)
            current_batch = {"start": entry["timestamp"], "end": None, "text": ""}
        current_batch["text"] += f" {entry['text']}"
    if current_batch["text"]:
        current_batch["end"] = current_batch["start"] + batch_size
        batches.append(current_batch)
    return batches


def summarize_batches_1(client, batches, max_attempts=5):
    summaries = []
    for batch in batches:
        attempts = 0
        while attempts < max_attempts:
            # before_section is last 5 batches if available
            before_section = ""
            for i in range(1, 6):
                if len(summaries) >= i:
                    before_section += summaries[-i]["summary"] + " "

            prompt = (
                f"Context: The transcript section is from a discussion or gameplay of the game *Rain World*. "
                f"Focus on key events, notable discoveries, or any unique occurrences within this section. "
                f"Avoid summarizing routine actions or commentary that doesn't add new, significant information.\n\n"
                f"Provide the summary as a JSON object in this format: {{'summary': ''}}. The summary should:\n"
                f"- Be a concise description of key points or special events, avoiding filler phrases or commentary.\n"
                f"- Exclude generic introductions like 'Player does' or 'In this section'.\n"
                f"- But most importantly, be no longer than 120 characters. Otherwise your response will be rejected.\n\n"
                f"Transcript Section:\n---\n{batch['text']}\n---\n\n"
                f"Context for reference only (do not include or summarize this): [{before_section}].\n\n"
                f"Generate only the JSON response. If no meaningful content is present, return {{'summary': ''}}."
            )

            result = client.generate_json_completion(prompt=prompt, stream=False)
            summary = result.get("summary", "").strip()
            if summary is not None and len(summary) <= 170:
                summary = re.sub(r"^(Rain World )?(Player )?", "", summary, flags=re.IGNORECASE)
                summaries.append({"start": batch["start"], "end": batch["end"], "summary": summary})
                one_line = summary.replace('\n', ' ')
                print(f"{batch['start']} - {batch['end']}: {one_line}")
                break
            else:
                attempts += 1
                print(f"Failed attempt {attempts} for {batch['start']} - {batch['end']}: {result}")
    return summaries


def summarize_batches(client, batches: List[Dict], max_attempts=5, max_workers=5) -> List[Dict]:
    summaries = []
    summaries_lock = Lock()

    def process_batch(index: int, batch: Dict):
        nonlocal summaries
        attempts = 0
        while attempts < max_attempts:
            with summaries_lock:
                before_section = " ".join(
                    summaries[-i]["summary"] for i in range(1, min(6, len(summaries) + 1))
                ).strip()

            prompt = (
                "Instructions:\n\n"
                "You are to generate a concise summary of a transcript section from the game **Rain World**. "
                "Focus exclusively on significant events that advance the game's narrative or gameplay. These significant events include:\n\n"
                "- **Obtaining new items or upgrades**\n"
                "- **Discovering or discussing lore or specific story details**\n"
                "- **Learning new information relevant to game progression**\n"
                "- **Finding new, relevant areas or encountering significant characters**\n\n"
                "Avoid including routine or insignificant actions, such as:\n\n"
                "- The player dying or losing progress\n"
                "- Random exploration without meaningful discoveries\n"
                "- General commentary or actions that don't add new, significant information\n\n"
                "**Summary Guidelines:**\n\n"
                "- Provide a concise description of the key significant events, avoiding filler phrases and unnecessary commentary.\n"
                "- Exclude generic introductions like 'Player does' or 'In this section'.\n"
                "- **The summary must be no longer than 120 characters. If it exceeds 120 characters, your response will be rejected.**\n\n"
                "**Format:**\n\n"
                "- Provide the summary as a JSON object in this exact format: `{'summary': ''}`\n"
                "- **Do not include any other text in your response.**\n\n"
                "**If there are no significant events in the transcript (as per the criteria above), return:** `{'summary': ''}`\n\n"
                "**Transcript Section:**\n\n"
                "---\n"
                f"{batch['text']}\n"
                # "---\n\n"
                # "*Note: The following context is for reference only and should not be included or summarized in your response: "
                # f"[{before_section}].*"
            )

            try:
                result = client.generate_json_completion(prompt=prompt, stream=False)
                summary = result.get("summary", "").strip()
            except InterruptedError as e:
                print(f"Error generating summary for {batch['start']} - {batch['end']}: {e}")
                break
            except Exception as e:
                print(f"Error generating summary for {batch['start']} - {batch['end']}: {e}")
                attempts += 1
                continue

            if summary and len(summary) <= 170:
                summary = re.sub(r"^(Rain World )?(Player )?(Streamer )?", "", summary, flags=re.IGNORECASE)
                summary = summary[0].upper() + summary[1:]
                with summaries_lock:
                    summaries.append({"start": batch["start"], "end": batch["end"], "summary": summary})
                one_line = summary.replace('\n', ' ')
                print(f"{batch['start']} - {batch['end']}: {one_line}")
                break
            else:
                attempts += 1
                print(f"Failed attempt {attempts} for {batch['start']} - {batch['end']}: {result}")

        if attempts == max_attempts:
            with summaries_lock:
                summaries.append({"start": batch["start"], "end": batch["end"], "summary": ""})
            print(f"{batch['start']} - {batch['end']}: <empty> after {max_attempts} attempts")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all batches to the executor with their respective indices
        futures = {executor.submit(process_batch, idx, batch): idx for idx, batch in enumerate(batches)}

        # Optionally, handle results as they complete
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"Batch {idx} generated an exception: {exc}")

    return summaries


def summarize_entire_transcript(client, sections: List[Dict], max_attempts=5, final_summary_max_length=2000) -> str:
    combined_summaries = " ".join(section["summary"] for section in sections if section["summary"])
    final_prompt = (
f"""
You are tasked with interpreting and summarizing gameplay data from **Rain World**. Focus on providing a meaningful and cohesive summary.
Avoid generic or repetitive descriptions, such as repeated deaths or insignificant actions. Provide concise and engaging insights.

**Gameplay Data:**

{combined_summaries}

**Required Output:**
Generate a JSON object summarizing the gameplay as: `{{'summary': 'YOUR SUMMARY HERE'}}`.
Do not provide an introduction or talk about the fact that this is Rain World gameplay.
"""
    )

    print("[overall] Generating the final coherent summary of the entire transcript.")
    complete_summary = ""
    attempts = 0
    while attempts < max_attempts:
        try:
            result = client.generate_json_completion(prompt=final_prompt, stream=False)
            summary = result.get("summary", "").strip()
            if summary:
                complete_summary = summary
                print("[overall] Complete summary generated successfully.")
                break
            else:
                attempts += 1
                print(f"[overall] Failed attempt {attempts} for complete summary: {result}")
        except InterruptedError as e:
            print(f"[overall] Error generating complete summary: {e}")
            break
        except Exception as e:
            print(f"[overall] Error generating complete summary: {e}")
            attempts += 1

    if not complete_summary:
        print(f"[overall] Failed to generate complete summary after {max_attempts} attempts.")

    print(f"[overall] Complete summary: {complete_summary}")

    return complete_summary


def parse_arguments():
    parser = argparse.ArgumentParser(description="Summarize a video transcript.")
    parser.add_argument("transcript_file", help="Path to the transcript file.")
    parser.add_argument("--output_file", default="none", help="Path to save the summary JSON file.")
    parser.add_argument("--batch_size", type=int, default=300, help="Batch size in seconds.")
    parser.add_argument("--max_attempts", type=int, default=5,
                        help="Maximum retry attempts for summarization per batch.")
    parser.add_argument("--base_url", required=True, help="Base URL for the completion API.")
    parser.add_argument("--model", required=True, help="Model name for the completion API.")
    return parser.parse_args()


def main():
    args = parse_arguments()
    client = CompletionClient(base_url=args.base_url, model=args.model)

    if args.output_file == "none":
        args.output_file = f"{args.transcript_file}-summary.json"

    entries = parse_transcript(args.transcript_file)

    batches = batch_transcript(entries, batch_size=args.batch_size)
    print(f"Transcript has {len(entries)} entries and {len(batches)} batches.")

    summaries = summarize_batches(client, batches, max_attempts=args.max_attempts)
    print(f"Summarized {len(summaries)} batches.")

    complete_summary = summarize_entire_transcript(client, summaries, max_attempts=args.max_attempts)

    result = {
        "batches": summaries,
        "full": complete_summary
    }

    with open(args.output_file, "w") as file:
        json.dump(result, file, indent=2)
    print(f"Summaries saved to {args.output_file}.")


if __name__ == "__main__":
    main()
