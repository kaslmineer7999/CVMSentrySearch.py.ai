from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import orjson
import requests


def get_all_log_files(base_url, visited=None):
  if visited is None:
    visited = set()

  clean_url = base_url.rstrip("/") + "/"
  if clean_url in visited:
    return []

  visited.add(clean_url)
  log_files = []
  print(f"Scanning directory: {base_url}")

  try:
    response = requests.get(base_url, timeout=15)
    response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(f"Error fetching {base_url}: {e}")
    return log_files

  soup = BeautifulSoup(response.text, "html.parser")

  for a_tag in soup.find_all("a"):
    href = a_tag.get("href")

    if (
        not href
        or href.startswith("?")
        or href.startswith("../")
        or href == "../"
        or href.startswith("#")
    ):
      continue

    if "webp" in href.lower() or href.rstrip("/") == "webp":
      continue

    full_url = urljoin(base_url, href)

    if href.endswith("/"):
      log_files.extend(get_all_log_files(full_url, visited))
    elif full_url.endswith((".json", ".log", ".txt")):
      log_files.append(full_url)

  return log_files


def process_single_file(file_url, target_user_lower, patterns_lower):
  """Downloads and parses a single log file concurrently, checking patterns."""
  file_chat_count = 0
  file_target_count = 0
  matches = []

  try:
    file_response = requests.get(file_url, timeout=15)
    file_response.raise_for_status()
    log_data = orjson.loads(file_response.content)
  except Exception:
    return file_chat_count, file_target_count, matches

  if not isinstance(log_data, list):
    log_data = [log_data]

  for entry in log_data:
    if entry.get("type") == "chat":
      file_chat_count += 1
      username = entry.get("username", "").lower()
      message = entry.get("message", "").lower()

      if username == target_user_lower:
        file_target_count += 1
        if any(pat in message for pat in patterns_lower):
          matches.append({
              "file": file_url,
              "timestamp": entry.get("timestamp"),
              "username": entry.get("username"),
              "message": entry.get("message"),
          })

  return file_chat_count, file_target_count, matches


def analyze_chat_logs(base_url, target_user, matching_patterns):
  print("Starting log discovery...")
  file_links = get_all_log_files(base_url)
  print(f"\nFound a total of {len(file_links)} log files to process.")
  print("Starting concurrent turbo-processing...\n")

  target_user_lower = target_user.lower()
  patterns_lower = [p.lower() for p in matching_patterns]

  total_chat_messages = 0
  total_target_messages = 0
  matched_messages = []

  # Process files concurrently using 16 threads
  with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {
        executor.submit(
            process_single_file, url, target_user_lower, patterns_lower
        ): url
        for url in file_links
    }

    for idx, future in enumerate(as_completed(futures), 1):
      url = futures[future]
      try:
        c_count, t_count, matches = future.result()
        total_chat_messages += c_count
        total_target_messages += t_count
        matched_messages.extend(matches)
        print(f"[{idx}/{len(file_links)}] Processed: {url}")
      except Exception as e:
        print(f"[{idx}/{len(file_links)}] Error processing {url}: {e}")

  # --- OUTPUT MATCHING MESSAGES FIRST ---
  print("\n" + "=" * 65)
  print(
      f"MATCHING MESSAGES FROM '{target_user}' matching patterns"
      f" {matching_patterns}:"
  )
  print("=" * 65)

  if not matched_messages:
    print("No matching messages found.")
  else:
    for idx, item in enumerate(matched_messages, 1):
      print(f"[{idx}] File: {item['file']}")
      print(f"    Timestamp: {item['timestamp']}")
      print(f"    Message: {item['message']}")
      print("-" * 45)

  pct_all = (
      (len(matched_messages) / total_chat_messages) * 100
      if total_chat_messages > 0
      else 0.0
  )
  pct_target = (
      (len(matched_messages) / total_target_messages) * 100
      if total_target_messages > 0
      else 0.0
  )

  # --- OUTPUT STATISTICS AT THE END ---
  print("\n" + "=" * 65)
  print("STATISTICS SUMMARY:")
  print("=" * 65)
  print("1. Based on ALL chat messages (global):")
  print(f"   Percentage: {pct_all:.2f}%")
  print(f"   Ratio: {len(matched_messages)} / {total_chat_messages}")
  print("-" * 45)
  print(f"2. Based on TOTAL messages sent by '{target_user}':")
  print(f"   Percentage: {pct_target:.2f}%")
  print(f"   Ratio: {len(matched_messages)} / {total_target_messages}")


if __name__ == "__main__":
  # Configuration parameters right at your fingertips
  TARGET_SITE = "https://sentry.gayfurri.es/"
  SEARCH_USER = "someone"
  SEARCH_PATTERNS = ["something"]

  analyze_chat_logs(TARGET_SITE, SEARCH_USER, SEARCH_PATTERNS)