from feedparser import parse
from datetime import datetime
from models import RSSFeedContent, db
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from pytz import timezone
import feedparser
from urllib.parse import urlparse
import warnings
from flask import current_app
from models import db, RSSFeed, RSSFeedContent

warnings.filterwarnings('ignore')


def adjust_datetime_with_timezone(date_string):
    """Convert various datetime strings to proper datetime objects."""
    try:
        if isinstance(date_string, datetime):
            return date_string
        
        # Try different date formats
        for date_format in [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
        ]:
            try:
                return datetime.strptime(date_string, date_format)
            except ValueError:
                continue
        
        # If all formats fail, use feedparser's date parser
        parsed_date = feedparser._parse_date(date_string)
        if parsed_date:
            return datetime(*parsed_date[:6])
            
        return datetime.now()
    except:
        return datetime.now()


def get_featured_image(post_url):
    """
    Fetch the Open Graph image (og:image) from the post URL.
    """
    try:
        response = requests.get(post_url, timeout=5)  # Fetch the HTML content
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                return og_image_tag['content']
    except Exception as e:
        print(f"Error fetching og:image from {post_url}: {e}")
    return None  # Return None if no og:image is found


def discover_feed_url(base_url):
    """Discover RSS/Atom feed URL from base URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }

        # First try to get the HTML and look for feed links
        try:
            response = requests.get(base_url, headers=headers, timeout=5, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for feed links in the HTML
            feed_links = []
            
            # Check link tags
            feed_links.extend(soup.find_all('link', 
                type=lambda t: t and ('rss' in t.lower() or 'atom' in t.lower() or 'xml' in t.lower())))
            feed_links.extend(soup.find_all('link', 
                rel='alternate', 
                type=lambda t: t and ('rss' in t.lower() or 'atom' in t.lower() or 'xml' in t.lower())))
            
            # Check a tags
            feed_links.extend(soup.find_all('a', 
                href=lambda h: h and ('rss' in h.lower() or 'feed' in h.lower() or 'atom' in h.lower())))
            
            for link in feed_links:
                href = link.get('href', '')
                if href:
                    feed_url = requests.compat.urljoin(base_url, href)
                    if is_valid_feed_url(feed_url):
                        print(f"Found feed URL in HTML: {feed_url}")
                        return base_url, feed_url
                        
        except Exception as e:
            print(f"Error checking HTML for feeds: {str(e)}")

        # If no feed found in HTML, try common paths
        common_paths = [
            '/feed',
            '/rss',
            '/feed/',
            '/rss/',
            '/atom.xml',
            '/feed.xml',
            '/rss.xml',
            '/feed/rss',
            '/feed/atom',
            '/rss/feed',
            '/index.xml',
            '/feeds',
            '/rss/news',
            '/rss/all',
            '/feed/rss2',
            '/rss/categorie/stiri',
            '/rss/rss.xml'
        ]

        for path in common_paths:
            try:
                feed_url = requests.compat.urljoin(base_url, path)
                print(f"Testing feed URL: {feed_url}")
                if is_valid_feed_url(feed_url):
                    print(f"Found valid feed URL: {feed_url}")
                    return base_url, feed_url
            except Exception:
                continue

        print(f"No valid feed URL found for {base_url}")
        return None, None

    except Exception as e:
        print(f"Error discovering feed URL: {str(e)}")
        return None, None


def is_valid_feed_url(url):
    """Check if URL points to a valid RSS/Atom feed."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'
        }
        response = requests.get(url, headers=headers, timeout=5, verify=False)
        return is_valid_feed(response.content)
    except:
        return False


def is_valid_feed(content):
    """Check if the content is a valid RSS or Atom feed."""
    try:
        parsed = feedparser.parse(content)
        
        # Check for required RSS/Atom elements
        if parsed.version and parsed.feed and parsed.entries:
            # Check if it's RSS
            if parsed.version.startswith('rss') or parsed.version.startswith('2.0'):
                return True
            # Check if it's Atom
            if parsed.version.startswith('atom'):
                return True
            
        return False
    except:
        return False


def process_feeds(user_id=None):
    """Process RSS feeds for all users or a specific user."""
    print("🔄 Fetching RSS feeds for all users...")
    
    try:
        feeds_query = RSSFeed.query
        if user_id:
            feeds_query = feeds_query.filter_by(user_id=user_id)
        feeds = feeds_query.all()

        processed_urls = set()  # Track processed URLs to avoid duplicates

        for feed in feeds:
            try:
                if feed.url in processed_urls:
                    continue
                    
                print(f"Processing feed: {feed.url}")
                processed_urls.add(feed.url)
                
                # Discover the feed URL first
                base_url, feed_url = discover_feed_url(feed.url)
                
                if not feed_url:
                    print(f"No valid feed URL found for {feed.url}")
                    continue

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'
                }
                
                response = requests.get(feed_url, headers=headers, timeout=10, verify=False)
                parsed_feed = feedparser.parse(response.content)
                
                if not parsed_feed.entries:
                    print(f"No entries found for {feed_url}")
                    continue

                print(f"Found {len(parsed_feed.entries)} entries for {feed_url}")

                # Process entries
                for entry in parsed_feed.entries[:20]:
                    try:
                        post_url = entry.get("link")
                        if not post_url:
                            continue

                        # Skip existing posts
                        existing_post = RSSFeedContent.query.filter_by(post_url=post_url).first()
                        if existing_post:
                            continue

                        # Extract post details
                        post_title = entry.get("title", "Untitled")
                        post_date_string = entry.get("published") or entry.get("updated")
                        post_date = adjust_datetime_with_timezone(post_date_string) if post_date_string else None
                        post_content = strip_html(entry.get("summary", "") or entry.get("content", [{"value": ""}])[0]["value"])
                        post_featured_image_url = get_featured_image(post_url)

                        new_post = RSSFeedContent(
                            feed_base_url=base_url,
                            post_title=post_title[:255],
                            post_date=post_date,
                            post_content=post_content,
                            post_featured_image_url=post_featured_image_url,
                            post_url=post_url
                        )
                        db.session.add(new_post)
                        print(f"Added new post: {post_title}")

                    except Exception as entry_error:
                        print(f"Error processing entry: {str(entry_error)}")
                        continue

                # Commit after each feed is processed successfully
                db.session.commit()

            except Exception as feed_error:
                print(f"Error processing feed {feed.url}: {str(feed_error)}")
                db.session.rollback()
                continue

        print("✅ All feeds processed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error in process_feeds: {str(e)}")
        db.session.rollback()
        return False


def process_feeds_old(user_id=None):
    """
    Process feeds for all users or a specific user.
    """
    from models import RSSFeed, RSSFeedContent

    try:
        feeds_query = RSSFeed.query
        if user_id:
            feeds_query = feeds_query.filter_by(user_id=user_id)
        feeds = feeds_query.all()

        processed_feeds = set()  # Keep track of processed feeds

        for feed in feeds:
            try:
                # Skip if we've already processed this feed
                if feed.url in processed_feeds:
                    continue
                
                processed_feeds.add(feed.url)
                print(f"Processing feed: {feed.url}")
                
                # Get base_url and feed_url
                base_url, feed_url = discover_feed_url(feed.url)
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/xml, application/rss+xml, text/xml, */*'
                }
                
                # Use feed_url for fetching
                response = requests.get(str(feed_url), headers=headers, timeout=10, verify=False)
                
                parsed_feed = feedparser.parse(response.content)
                
                if not parsed_feed.entries:
                    print(f"No entries found for {feed_url}")
                    continue
                
                print(f"Found {len(parsed_feed.entries)} entries for {feed_url}")
                
                # Process entries
                for entry in parsed_feed.entries[:20]:
                    try:
                        post_url = entry.get("link")
                        if not post_url:
                            continue

                        # Skip existing posts
                        existing_post = RSSFeedContent.query.filter_by(post_url=post_url).first()
                        if existing_post:
                            continue

                        # Extract post details
                        post_title = entry.get("title", "Untitled")
                        post_date_string = entry.get("published") or entry.get("updated")
                        post_date = adjust_datetime_with_timezone(post_date_string) if post_date_string else None
                        post_content = strip_html(entry.get("summary", "") or entry.get("content", [{"value": ""}])[0]["value"])
                        post_featured_image_url = get_featured_image(post_url)

                        new_post = RSSFeedContent(
                            feed_base_url=str(base_url),  # Convert to string explicitly
                            post_title=post_title[:255],
                            post_date=post_date,
                            post_content=post_content,
                            post_featured_image_url=post_featured_image_url,
                            post_url=post_url
                        )
                        db.session.add(new_post)
                        print(f"Added new post: {post_title}")
                    except Exception as entry_error:
                        print(f"Error processing entry: {str(entry_error)}")
                        continue

            except Exception as e:
                print(f"Error processing feed {feed.url}: {str(e)}")
                continue

        db.session.commit()
        print("✅ All feeds processed successfully!")
        
    except Exception as e:
        print(f"❌ Error in process_feeds: {str(e)}")
        db.session.rollback()

    results = []
    for feed in feeds:
        print(f"Processing feed: {feed.url}")

        # Discover the RSS/Atom feed URL if not already provided
        discovered_feed_url = discover_feed_url(feed.url)
        if not discovered_feed_url:
            print(f"No valid feed found for {feed.url}")
            results.append({
                "feed_url": feed.url,
                "parsed_url": "No valid feed found",
                "post_titles": []
            })
            continue

        # Parse the discovered feed
        parsed_feed = parse(discovered_feed_url)
        if parsed_feed.bozo:
            print(f"Error parsing feed {discovered_feed_url}: {parsed_feed.bozo_exception}")
            results.append({
                "feed_url": feed.url,
                "parsed_url": discovered_feed_url,
                "post_titles": [],
                "status": f"Error parsing feed: {parsed_feed.bozo_exception}"
            })
            continue

        # Prepare data for UI display
        post_titles = [entry.get("title", "Untitled") for entry in parsed_feed.entries[:5]]
        results.append({
            "feed_url": feed.url,
            "parsed_url": discovered_feed_url,
            "post_titles": post_titles
        })

    return results

def fix_existing_feed_base_urls():
    """One-time fix for existing feed base URLs in the database."""
    try:
        # Get all unique feed base URLs
        unique_feeds = db.session.query(RSSFeedContent.feed_base_url).distinct().all()
        
        for (feed_url,) in unique_feeds:
            base_url, _ = discover_feed_url(feed_url)
            if base_url and base_url != feed_url:
                # Update all entries with this feed base URL
                RSSFeedContent.query.filter_by(feed_base_url=feed_url).update(
                    {"feed_base_url": base_url}
                )
        
        db.session.commit()
        print("✅ Successfully fixed existing feed base URLs")
        
    except Exception as e:
        print(f"❌ Error fixing feed base URLs: {str(e)}")
        db.session.rollback()

def strip_html(html_content):
    """Remove HTML tags and decode HTML entities from content."""
    if not html_content:
        return ""
    
    try:
        # Remove HTML tags
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        # Replace multiple spaces with single space
        text = ' '.join(text.split())
        
        # Decode HTML entities
        text = BeautifulSoup(text, 'html.parser').get_text()
        
        return text
    except Exception as e:
        print(f"Error stripping HTML: {str(e)}")
        return html_content