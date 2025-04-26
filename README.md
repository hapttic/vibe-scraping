# Vibe Scraping

Lightweight web crawler using Scrapy for deep web crawling.

## Features

- Deep web crawling with configurable depth
- Fast parallel processing with Scrapy
- Saves both HTML and extracted text content
- Simple API with minimal dependencies

## Installation

```bash
# Clone the repository
git clone https://github.com/l0rtk/vibe-scraping.git
cd vibe-scraping

# Install dependencies
pip install scrapy

# Install the package
pip install -e .
```

## Quick Usage

```python
from vibe_scraping.crawler import WebCrawler

# Create and run crawler
crawler = WebCrawler(
    start_url="https://example.com",
    save_path="./crawled_data",
    max_depth=3,
    max_pages=100
)

result = crawler.crawl()
print(f"Crawled {result['pages_crawled']} pages!")
```

## Command Line Usage

```bash
# Basic usage
python -m vibe_scraping.cli https://example.com -o crawled_data -d 3 -p 100

# Show help
python -m vibe_scraping.cli --help
```

### Docker

```
docker build -t vibe-scraper .

docker run --name vibe-scraper \
  -v "$(pwd)/crawler_data:/app/data_to_upload" \
  vibe-scraper \
  --websites https://alia.ge https://ambebi.ge https://interpressnews.ge https://palitravideo.ge https://primetime.ge \
  --max-pages 100 \
  --max-depth 3 \

```

## License

MIT License
