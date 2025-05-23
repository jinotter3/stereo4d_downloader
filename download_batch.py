import os
import subprocess
import argparse
import time
import random
from tqdm import tqdm
import concurrent.futures

def read_urls(file_path):
    """Read URLs from a text file."""
    with open(file_path, 'r') as f:
        # Assuming each line contains one URL
        urls = [line.strip() for line in f if line.strip()]
    return urls

def read_downloaded_urls(file_path):
    """Read already downloaded URLs from a file."""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            downloaded_urls = [line.strip() for line in f if line.strip()]
        return set(downloaded_urls)
    return set()

def extract_video_id_from_url(url):
    """Extract video ID from a YouTube URL."""
    if 'youtube.com/watch?v=' in url:
        return url.split('youtube.com/watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    else:
        return url  # Assume the URL is already a video ID

def download_video(url, output_dir, retry_count=3, verbose=False, cookies_file=None, cookies_from_browser=None):
    """Download a video from YouTube using yt-dlp with retries."""
    video_id = extract_video_id_from_url(url)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    
    # Check if video already exists
    for ext in ['mp4', 'mkv', 'webm']:
        if os.path.exists(os.path.join(output_dir, f"{video_id}.{ext}")):
            return {"status": "already_exists", "url": url, "video_id": video_id}
    
    # Download the video with retries
    for attempt in range(retry_count):
        try:
            cmd = [
                "yt-dlp",
                url,
                "-f", "313",  # 4K webm
                "-o", output_template,
                "--no-playlist",
                "--no-check-certificate",  # Skip HTTPS certificate validation
                "--ignore-errors",         # Continue on download errors
                # "--extractor-arg", "youtube:player_client=android_vr"
            ]
            
            # Add cookies if provided
            if cookies_file:
                cmd.extend(["--cookies", cookies_file])
            if cookies_from_browser:
                cmd.extend(["--cookies-from-browser", cookies_from_browser])
            
            if verbose:
                print(f"Running command: {' '.join(cmd)}")
            
            # Capture both stdout and stderr
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                if verbose or attempt == retry_count - 1:
                    print(f"Error downloading {url}:")
                    print(f"STDOUT: {stdout}")
                    print(f"STDERR: {stderr}")
                
                # Check for specific error types
                if "Sign in to confirm you're not a bot" in stderr or "Sign in to confirm you're not a bot" in stdout:
                    if not (cookies_file or cookies_from_browser):
                        return {
                            "status": "error", 
                            "url": url, 
                            "video_id": video_id, 
                            "error": "Authentication required. Use --cookies-file or --cookies-from-browser",
                            "details": stderr
                        }
                
                # If "Video unavailable" is in the output, stop retrying
                if "Video unavailable" in stdout or "Video unavailable" in stderr:
                    return {
                        "status": "error", 
                        "url": url, 
                        "video_id": video_id, 
                        "error": "Video unavailable (removed or private)",
                        "details": stdout + stderr
                    }
                
                # Try with alternative format on second attempt
                if attempt == 1:
                    cmd = [
                        "yt-dlp",
                        url,
                        "-f", "bestvideo[ext=webm]",  # Try any format
                        "-o", output_template,
                        "--no-playlist",
                        "--no-check-certificate",
                        "--extractor-arg", "youtube:player_client=android_vr"
                    ]
                    
                    # Add cookies if provided
                    if cookies_file:
                        cmd.extend(["--cookies", cookies_file])
                    if cookies_from_browser:
                        cmd.extend(["--cookies-from-browser", cookies_from_browser])
                    
                    if verbose:
                        print(f"Trying alternate format: {' '.join(cmd)}")
                    
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        return {"status": "success", "url": url, "video_id": video_id}
                
                if attempt < retry_count - 1:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Retry {attempt + 1}/{retry_count} for {url} after {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                else:
                    return {
                        "status": "error", 
                        "url": url, 
                        "video_id": video_id, 
                        "error": f"Failed after {retry_count} attempts",
                        "details": stdout + stderr
                    }
            else:
                return {"status": "success", "url": url, "video_id": video_id}
            
        except Exception as e:
            if attempt < retry_count - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Exception during download of {url}: {e}")
                print(f"Retry {attempt + 1}/{retry_count} after {wait_time:.2f} seconds")
                time.sleep(wait_time)
            else:
                return {"status": "error", "url": url, "video_id": video_id, "error": str(e)}

def download_batch(urls, output_dir, downloaded_file, max_workers=10, verbose=False, cookies_file=None, cookies_from_browser=None):
    """Download a batch of videos with status tracking."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read already downloaded URLs
    downloaded_urls = read_downloaded_urls(downloaded_file)
    print(f"Found {len(downloaded_urls)} already downloaded URLs")
    
    # Filter out already downloaded URLs
    urls_to_download = [url for url in urls if url not in downloaded_urls]
    
    print(f"Downloading {len(urls_to_download)} URLs (skipping {len(urls) - len(urls_to_download)} already downloaded)")
    
    # If no URLs to download, return
    if not urls_to_download:
        print("No new URLs to download")
        return
    
    # Download URLs
    successful_urls = []
    failed_urls = []
    
    # For single-threaded approach
    if max_workers == 1:
        for url in tqdm(urls_to_download, desc="Downloading videos"):
            result = download_video(url, output_dir, verbose=verbose, 
                                   cookies_file=cookies_file, 
                                   cookies_from_browser=cookies_from_browser)
            
            if result["status"] in ["success", "already_exists"]:
                successful_urls.append(url)
                # Append to downloaded file immediately
                with open(downloaded_file, 'a') as f:
                    f.write(url + '\n')
            else:
                failed_urls.append({
                    "url": url, 
                    "error": result.get("error", "Unknown error"),
                    "details": result.get("details", "")
                })
    else:
        # Parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(download_video, url, output_dir, verbose=verbose,
                                           cookies_file=cookies_file, 
                                           cookies_from_browser=cookies_from_browser): url for url in urls_to_download}
            
            for future in tqdm(concurrent.futures.as_completed(future_to_url), total=len(future_to_url), desc="Downloading videos"):
                url = future_to_url[future]
                result = future.result()
                
                if result["status"] in ["success", "already_exists"]:
                    successful_urls.append(url)
                    # Append to downloaded file immediately
                    with open(downloaded_file, 'a') as f:
                        f.write(url + '\n')
                else:
                    failed_urls.append({
                        "url": url, 
                        "error": result.get("error", "Unknown error"),
                        "details": result.get("details", "")
                    })
    
    print(f"Downloaded {len(successful_urls)} videos successfully")
    print(f"Failed to download {len(failed_urls)} videos")
    
    # Write failed URLs to file for later retry
    failed_file = downloaded_file.replace('downloaded_', 'failed_')
    with open(failed_file, 'w') as f:
        for failed in failed_urls:
            f.write(f"{failed['url']}\t{failed['error']}\n")

def batch_download_from_file(url_file, output_dir, batch_size=100, max_workers=10, verbose=False, cookies_file=None, cookies_from_browser=None):
    """Download videos in batches from a URL file."""
    # Determine the base name for the downloaded URLs file
    file_base = os.path.basename(url_file).split('.')[0]  # e.g., "train" or "test"
    downloaded_file = f"downloaded_{file_base}_urls.txt"
    
    # Read all URLs
    all_urls = read_urls(url_file)
    print(f"Found {len(all_urls)} URLs in {url_file}")
    
    # Read already downloaded URLs
    downloaded_urls = read_downloaded_urls(downloaded_file)
    print(f"Found {len(downloaded_urls)} already downloaded URLs")
    
    # Filter out already downloaded URLs
    urls_to_download = [url for url in all_urls if url not in downloaded_urls]
    print(f"Remaining URLs to download: {len(urls_to_download)}")
    
    # Process in batches
    total_batches = (len(urls_to_download) + batch_size - 1) // batch_size
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(urls_to_download))
        batch_urls = urls_to_download[start_idx:end_idx]
        
        print(f"\nProcessing batch {batch_num + 1}/{total_batches} ({len(batch_urls)} URLs)")
        download_batch(batch_urls, output_dir, downloaded_file, max_workers, verbose, cookies_file, cookies_from_browser)
        
        print(f"Batch {batch_num + 1}/{total_batches} completed")
        print(f"Total progress: {min(end_idx, len(urls_to_download))}/{len(urls_to_download)} URLs processed")

        sleep_time = random.randint(5, 60)
        print(f"Sleeping for {sleep_time} seconds")
        time.sleep(sleep_time)

def check_yt_dlp_installation():
    """Check if yt-dlp is installed and working properly."""
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"yt-dlp is installed (version: {result.stdout.strip()})")
            return True
        else:
            print("yt-dlp is installed but returned an error")
            print(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("yt-dlp is not installed. Please install it with:")
        print("pip install yt-dlp")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YouTube videos from URL text files in batches")
    parser.add_argument("--url_file", required=True, help="Text file containing URLs to download (train_urls.txt or test_urls.txt)")
    parser.add_argument("--output_dir", required=True, help="Directory to save downloaded videos")
    parser.add_argument("--batch_size", type=int, default=50, help="Number of URLs to download in each batch")
    parser.add_argument("--max_workers", type=int, default=10, help="Maximum number of concurrent downloads")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output including yt-dlp messages")
    parser.add_argument("--check", action="store_true", help="Check if yt-dlp is installed correctly")
    parser.add_argument("--cookies-file", help="Path to cookies file for YouTube authentication")
    parser.add_argument("--cookies-from-browser", help="Extract cookies from browser (e.g., 'chrome', 'firefox', 'edge', 'safari')")
    
    args = parser.parse_args()
    
    # Check if yt-dlp is installed if --check flag is provided
    if args.check:
        check_yt_dlp_installation()
        exit()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Start batch downloads
    batch_download_from_file(
        args.url_file, 
        args.output_dir, 
        args.batch_size, 
        args.max_workers,
        verbose=args.verbose,
        cookies_file=args.cookies_file,
        cookies_from_browser=args.cookies_from_browser
    )