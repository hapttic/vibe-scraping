from crawl_and_upload import crawler_func
import argparse
import sys
import time

# Default website to crawl
default_website = "https://www.ambebi.ge/"

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

if __name__ == "__main__":
    args = parse_args()
    
    # Use provided website or fall back to default
    website = args.website if args.website else default_website
    
    def run_crawl():
        print(f"Starting crawl for website: {website}")
        
        # Run a single crawl for the website
        result = crawler_func(
            websites=website,  # crawler_func already handles single string or list
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            remove_local_files=args.remove_local,
            bucket=args.bucket
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
    
    # Run once or in continuous loop
    if args.no_loop:
        run_crawl()
    else:
        try:
            while True:
                run_crawl()
                wait_time = args.wait_time
                print(f"\nWaiting {wait_time} seconds before next crawl...")
                time.sleep(wait_time)
        except KeyboardInterrupt:
            print("\nCrawl process terminated by user")
            sys.exit(0) 