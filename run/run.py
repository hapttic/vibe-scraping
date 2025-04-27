from crawl_and_upload import crawler_func
import argparse
import sys
import time
import subprocess
import os
import signal
import logging
import atexit
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Default website to crawl
default_website = "https://www.ambebi.ge/"

# Track child processes for cleanup
child_processes = []

# Flag to control the main loop
running = True

def cleanup_children():
    """Clean up any child processes when parent exits"""
    for proc in child_processes:
        if proc.poll() is None:  # If process is still running
            logger.info(f"Terminating child process {proc.pid}")
            try:
                proc.terminate()
                # Give it a moment to terminate gracefully
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()  # Force kill if still running
            except Exception as e:
                logger.error(f"Error terminating child process: {e}")

# Handle SIGTERM signal (Docker stop)
def handle_sigterm(signum, frame):
    global running
    logger.info("Received SIGTERM signal. Shutting down gracefully...")
    running = False
    cleanup_children()
    # Don't exit immediately - let the main loop exit gracefully

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
    parser.add_argument('--single-crawl', action='store_true', help='Internal flag for single-crawl subprocess')
    parser.add_argument('--crawl-args', type=str, help='JSON encoded arguments for crawler (internal use)')
    return parser.parse_args()

def run_single_crawl_process(website, max_pages, max_depth, remove_local, bucket):
    """Run a single crawl in a dedicated subprocess to avoid reactor restart issues"""
    
    # Create a JSON string with the arguments to pass to the subprocess
    crawl_args = {
        'website': website,
        'max_pages': max_pages,
        'max_depth': max_depth,
        'remove_local': remove_local,
        'bucket': bucket
    }
    
    # Get the current script path
    script_path = os.path.abspath(sys.argv[0])
    
    # Launch a new process with the --single-crawl flag
    cmd = [
        sys.executable, 
        script_path, 
        '--single-crawl',
        '--crawl-args', json.dumps(crawl_args)
    ]
    
    logger.info(f"Starting single crawl subprocess: {' '.join(cmd)}")
    
    # Run the subprocess and capture output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1  # Line buffered
    )
    
    # Track the process
    child_processes.append(process)
    
    # Stream the output in real-time
    for line in process.stdout:
        print(line, end='')
    
    # Wait for process to complete
    process.wait()
    
    # Remove from tracked processes
    if process in child_processes:
        child_processes.remove(process)
    
    return {'success': process.returncode == 0}

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
    """Wait for the specified time, with clean interruption handling"""
    global running
    
    logger.info(f"Waiting {wait_time} seconds before next crawl...")
    
    # Wait in smaller chunks to allow for clean interruption
    chunk_size = 5  # Check every 5 seconds
    elapsed = 0
    
    while elapsed < wait_time and running:
        try:
            sleep_time = min(chunk_size, wait_time - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
        except KeyboardInterrupt:
            logger.info("Interrupted during wait period")
            return False
    
    return running  # Continue if still running

if __name__ == "__main__":
    # Register for cleanup on exit
    atexit.register(cleanup_children)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)  # Also handle Ctrl+C similarly
    
    args = parse_args()
    
    # If this is a single-crawl subprocess, just run the crawl and exit
    if args.single_crawl:
        if not args.crawl_args:
            logger.error("Missing crawl arguments for single-crawl mode")
            sys.exit(1)
        
        # Parse the crawl arguments
        try:
            crawl_args = json.loads(args.crawl_args)
            # Run the crawl with the provided arguments
            result = run_single_crawl(
                crawl_args['website'],
                crawl_args['max_pages'],
                crawl_args['max_depth'],
                crawl_args['remove_local'],
                crawl_args['bucket']
            )
            sys.exit(0 if result['success'] else 1)
        except Exception as e:
            logger.error(f"Error in single-crawl mode: {e}")
            sys.exit(1)
    
    # Main process - use provided website or fall back to default
    website = args.website if args.website else default_website
    
    # Run once or in continuous loop
    if args.no_loop:
        run_single_crawl_process(website, args.max_pages, args.max_depth, args.remove_local, args.bucket)
    else:
        try:
            # Main loop - keep running crawls until interrupted
            while running:
                # Run a crawl in a subprocess
                run_single_crawl_process(website, args.max_pages, args.max_depth, args.remove_local, args.bucket)
                
                # Wait for the next crawl, exit if interrupted or signaled to stop
                if not wait_for_next_crawl(args.wait_time):
                    break
                
        except KeyboardInterrupt:
            logger.info("Crawl process terminated by user")
            running = False
    
    logger.info("Crawler main process exiting...")
    cleanup_children()
    sys.exit(0)