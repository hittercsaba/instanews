from feedparser import parse
from datetime import datetime
from models import RSSFeedContent, db
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from pytz import timezone


def adjust_datetime_with_timezone(date_string):
    """
    Parse a datetime string with timezone information and adjust it to the desired timezone.
    """
    try:
        # Parse the date string with timezone info
        dt = parser.parse(date_string)

        # Convert to the target timezone (e.g., Europe/Bucharest)
        target_tz = timezone("Europe/Bucharest")
        dt_with_tz = dt.astimezone(target_tz)

        return dt_with_tz
    except Exception as e:
        print(f"Error parsing datetime: {e}")
        return None


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
    """
    Attempt to discover the RSS or Atom feed URL from a base URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(base_url, headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"Error fetching base URL {base_url}: HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for <link> tags pointing to RSS or Atom feeds
        feed_links = soup.find_all('link', rel='alternate')
        for link in feed_links:
            feed_type = link.get('type', '')
            href = link.get('href', '')
            if 'rss' in feed_type or 'atom' in feed_type:
                return requests.compat.urljoin(base_url, href)

        # Fallback: Test common feed paths
        fallback_paths = ['/rss', '/feed', '/atom.xml', '/rss.xml']
        for path in fallback_paths:
            test_url = requests.compat.urljoin(base_url, path)
            print(f"Testing fallback feed URL: {test_url}")
            test_feed = parse(test_url)
            if not test_feed.bozo:
                print(f"Discovered fallback feed URL: {test_url}")
                return test_url

        print(f"No RSS/Atom feed found on {base_url}")
        return None
    except Exception as e:
        print(f"Error discovering feed URL for {base_url}: {e}")
        return None


def strip_html(content):
    """
    Remove HTML tags from the content string.
    """
    try:
        return BeautifulSoup(content, 'html.parser').get_text()
    except Exception as e:
        print(f"Error stripping HTML: {e}")
        return content


def process_feeds(user_id=None):
    """
    Process feeds for all users or a specific user.
    """
    from models import RSSFeed, RSSFeedContent

    feeds = RSSFeed.query.filter_by(user_id=user_id).all() if user_id else RSSFeed.query.all()
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

        # Process entries in the feed
        for entry in parsed_feed.entries[:20]:  # Limit to 20 entries
            post_url = entry.get("link")
            if not post_url:
                continue

            # Avoid duplicate entries
            existing_post = RSSFeedContent.query.filter_by(post_url=post_url).first()
            if existing_post:
                print(f"Duplicate post skipped: {post_url}")
                continue

            # Extract post details
            post_title = entry.get("title", "Untitled")
            post_date_string = entry.get("published") or entry.get("updated")
            post_date = adjust_datetime_with_timezone(post_date_string) if post_date_string else None
            post_content = strip_html(entry.get("summary", "") or entry.get("content", [{"value": ""}])[0]["value"])
            post_featured_image_url = get_featured_image(post_url)

            # Add the new post to the database
            new_post = RSSFeedContent(
                feed_base_url=feed.url,
                post_title=post_title[:255],  # Truncate title to fit database column size
                post_date=post_date,
                post_content=post_content,
                post_featured_image_url=post_featured_image_url,
                post_url=post_url
            )
            db.session.add(new_post)

        # Commit the database transaction
        try:
            db.session.commit()
            print(f"Feed processed successfully: {discovered_feed_url}")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving feed entries for {discovered_feed_url}: {e}")

        # Prepare data for UI display
        post_titles = [entry.get("title", "Untitled") for entry in parsed_feed.entries[:5]]
        results.append({
            "feed_url": feed.url,
            "parsed_url": discovered_feed_url,
            "post_titles": post_titles
        })

    return results