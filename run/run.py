from crawl_and_upload import crawler_func
import argparse
import sys
import time
import subprocess
import os
import signal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Default website to crawl
default_website = "https://www.ambebi.ge/"

# Handle SIGTERM signal (Docker stop)
def handle_sigterm(signum, frame):
    logger.info("Received SIGTERM signal. Shutting down gracefully...")
    sys.exit(0)

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

# The proper restart function that works with Scrapy's reactor
def restart_script_for_next_crawl(args_dict, wait_time):
    """Wait for the specified time, then restart the script with a new process"""
    logger.info(f"Waiting {wait_time} seconds before next crawl...")
    
    try:
        # Wait for specified time, but check every few seconds if we should exit
        chunk_size = 5  # Check every 5 seconds
        for _ in range(0, wait_time, chunk_size):
            time.sleep(min(chunk_size, wait_time - _))
            # Check if we should continue (could add logic to exit early)
    except KeyboardInterrupt:
        logger.info("Crawl process terminated by user during wait period")
        sys.exit(0)
    
    # Get the current script path
    script_path = os.path.abspath(sys.argv[0])
    logger.info(f"Will restart using script path: {script_path}")
    
    # Build arguments list from the original arguments
    new_args = [sys.executable, script_path]
    for arg, value in args_dict.items():
        if arg == 'no_loop' or arg == 'remove_local':
            # Skip these or handle differently
            continue
        if value is not None:
            new_args.extend([f'--{arg.replace("_", "-")}', str(value)])
    
    # Add special flags
    if not args_dict.get('remove_local', True):
        new_args.append('--no-remove-local')
    
    # Always run with no_loop=False for the next iteration
    
    # Execute the new process with the same arguments
    logger.info(f"Restarting crawler with command: {' '.join(new_args)}")
    
    # Start the new process, ensuring it doesn't inherit file descriptors
    # that might cause issues with Docker
    process = subprocess.Popen(
        new_args,
        close_fds=True,
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    # Log that we're exiting
    logger.info("Crawler parent process exiting after starting child...")
    sys.exit(0)

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
            # Run a single crawl
            run_single_crawl(website, args.max_pages, args.max_depth, args.remove_local, args.bucket)
            
            # Convert args to dict for easier handling in restart function
            args_dict = vars(args)
            
            # Restart the script for the next crawl
            restart_script_for_next_crawl(args_dict, args.wait_time)
            
        except KeyboardInterrupt:
            logger.info("Crawl process terminated by user")
            sys.exit(0)