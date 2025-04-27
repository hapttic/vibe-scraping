from crawl_and_upload import crawler_func
import argparse
import sys
import time
import subprocess
import os
import signal

# Default website to crawl
default_website = "https://www.ambebi.ge/"

# Flag to track if we need to exit
exit_flag = False

# Handle SIGTERM signal (Docker stop)
def handle_sigterm(signum, frame):
    global exit_flag
    print("\nReceived SIGTERM signal. Shutting down gracefully...")
    exit_flag = True

def parse_args():
    parser = argparse.ArgumentParser(description='Web crawler with S3 upload')
    parser.add_argument('--website', '-w', type=str, help='Website URL to crawl', default=None)
    parser.add_argument('--max-pages', '-p', type=int, default=500, help='Maximum number of pages to crawl')
    parser.add_argument('--max-depth', '-d', type=int, default=5, help='Maximum crawl depth')
    parser.add_argument('--no-remove-local', action='store_false', dest='remove_local', 
                        help='Do not remove local files after upload')
    parser.add_argument('--bucket', '-b', type=str, default="first-hapttic-bucket", 
                        help='S3 bucket name')
    parser.add_argument('--no-loop', action='store_true', help='Run once without continuous looping')
    parser.add_argument('--wait-time', type=int, default=3600, help='Wait time between crawls in seconds (default: 1 hour)')
    return parser.parse_args()

def run_single_crawl(website, max_pages, max_depth, remove_local, bucket):
    """Run a single crawl for the given website"""
    print(f"Starting crawl for website: {website}")
    
    # Run a single crawl for the website
    result = crawler_func(
        websites=website,  # crawler_func already handles single string or list
        max_pages=max_pages,
        max_depth=max_depth,
        remove_local_files=remove_local,
        bucket=bucket
    )
    
    # Print summary
    print("\nCrawl and upload summary:")
    print(f"Crawled {result['pages_crawled']} pages from {website}")
    
    if result['success']:
        print(f"Uploaded {result['files_uploaded']} files ({result['bytes_uploaded'] / (1024*1024):.2f} MB)")
        print(f"Skipped {result['files_skipped']} existing files")
        print(f"Files stored in S3 bucket: {result['bucket']} with prefixes:")
        for prefix in result['s3_prefixes']:
            print(f"  - {prefix}")
        if result.get('local_files_removed', False):
            print("Local files have been removed.")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}") 
    
    return result

def wait_for_next_crawl(wait_time):
    """Wait for the specified time before next crawl, with clean interruption handling"""
    global exit_flag
    print(f"\nWaiting {wait_time} seconds before next crawl...")
    
    # Wait in smaller chunks to allow for clean interruption
    chunks = 10  # Check for exit flag every few seconds
    chunk_time = max(1, wait_time // chunks)
    remaining = wait_time
    
    while remaining > 0 and not exit_flag:
        try:
            time_to_sleep = min(chunk_time, remaining)
            time.sleep(time_to_sleep)
            remaining -= time_to_sleep
        except KeyboardInterrupt:
            print("\nCrawl process terminated by user during wait period")
            return False
    
    return not exit_flag  # Return True if we should continue, False if we should exit

# For backward compatibility
def restart_script_for_next_crawl(args_dict, wait_time):
    """Legacy function kept for backward compatibility"""
    print("WARNING: Using restart mechanism is deprecated, using internal loop instead")
    if wait_for_next_crawl(wait_time):
        # We'll handle the loop in the main function now
        return True
    else:
        sys.exit(0)

# Solution 2: Alternative function to use if the process restart isn't desirable
def run_as_separate_process(website, max_pages, max_depth, remove_local, bucket):
    """Run the crawler as a separate process"""
    import multiprocessing
    
    # Create a new process for the crawler
    p = multiprocessing.Process(
        target=run_single_crawl, 
        args=(website, max_pages, max_depth, remove_local, bucket)
    )
    p.start()
    p.join()  # Wait for the process to finish
    
    return {"success": p.exitcode == 0}

if __name__ == "__main__":
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    args = parse_args()
    
    # Use provided website or fall back to default
    website = args.website if args.website else default_website
    
    # Run once or in continuous loop
    if args.no_loop:
        run_single_crawl(website, args.max_pages, args.max_depth, args.remove_local, args.bucket)
    else:
        try:
            while not exit_flag:
                # Run a crawl
                run_single_crawl(website, args.max_pages, args.max_depth, args.remove_local, args.bucket)
                
                # Wait for the next crawl, exit if interrupted
                if not wait_for_next_crawl(args.wait_time):
                    break
                
        except KeyboardInterrupt:
            print("\nCrawl process terminated by user")
    
    print("Crawler process exiting...")
    sys.exit(0)