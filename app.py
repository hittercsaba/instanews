import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from models import db, User, RSSFeed, RSSFeedContent, ReadLog
from rssfeedparser import process_feeds, fix_existing_feed_base_urls
from forms import RegistrationForm, LoginForm
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from urllib.parse import urlparse, urljoin
import hashlib
import time
import feedparser
import ipaddress
import socket
import tldextract

# Initialize Scheduler with proper configuration
scheduler = BackgroundScheduler({
    'apscheduler.timezone': 'UTC',
    'apscheduler.job_defaults.max_instances': 1
})

def fetch_rss_feed_updates():
    """Fetch RSS feed updates for all users."""
    try:
        with app.app_context():
            print("🔄 Fetching RSS feeds for all users...")
            
            # Configure feedparser to ignore content type
            feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            
            # Add this before processing feeds
            if hasattr(feedparser, 'PREFERRED_XML_PARSERS'):
                # Try all available parsers
                feedparser.PREFERRED_XML_PARSERS = ['libxml2', 'etree', 'html.parser']

            process_feeds(None)
            print("✅ RSS feeds processed successfully!")
    except Exception as e:
        print(f"❌ Error during RSS feed update: {e}")

# Remove duplicate scheduler initialization and improve the run_scheduler function
def run_scheduler():
    try:
        if not scheduler.running:
            scheduler.add_job(
                func=fetch_rss_feed_updates,
                trigger="interval",
                minutes=5,
                id="rss_feed_job",
                replace_existing=True
            )
            scheduler.start()
            print("🚀 Scheduler started successfully.")
    except Exception as e:
        print(f"❌ Error starting scheduler: {e}")

# Initialize Flask app before running scheduler
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'another_strong_key_here_supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'mysql+pymysql://rss_db_user:rssdbuserpassword@localhost/rss_db'
)


# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'



def discover_favicon_url(base_url):
    """Discover the favicon URL from the base URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(base_url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        favicon_link = soup.find('link', rel='icon')
        if favicon_link and favicon_link.get('href'):
            return requests.compat.urljoin(base_url, favicon_link['href'])

        # Fallback to default favicon
        default_favicon = requests.compat.urljoin(base_url, '/favicon.ico')
        response = requests.head(default_favicon, timeout=5)
        if response.status_code == 200:
            return default_favicon

        return None
    except Exception as e:
        print(f"Error discovering favicon for {base_url}: {e}")
        return None

# Ensure tables are created when the app context is initialized
with app.app_context():
    db.create_all()

# User Loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data)
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')

    return render_template('register.html', form=form)

@app.route('/')
@login_required
def dashboard():
    user_id = current_user.id

    # Get the current user's feed content
    total_base_urls = db.session.query(RSSFeedContent.feed_base_url)\
        .join(RSSFeed, RSSFeedContent.feed_base_url == RSSFeed.url)\
        .filter(RSSFeed.user_id == current_user.id)\
        .distinct()\
        .count()

    # Fetch available RSS feeds count for the current user
    total_rss_feeds = db.session.query(RSSFeedContent)\
        .join(RSSFeed, RSSFeedContent.feed_base_url == RSSFeed.url)\
        .filter(RSSFeed.user_id == current_user.id)\
        .count()

    # Fetch total read feeds count
    total_read_feeds = ReadLog.query.filter_by(user_id=user_id).count()

    # Fetch news count per source per day (last 7 days)
    last_7_days = datetime.now(timezone.utc) - timedelta(days=7)
    news_by_day = db.session.query(
        RSSFeedContent.feed_base_url,
        db.func.date(RSSFeedContent.created_at),
        db.func.count(RSSFeedContent.id)
    ).filter(RSSFeedContent.created_at >= last_7_days).group_by(
        RSSFeedContent.feed_base_url, db.func.date(RSSFeedContent.created_at)
    ).all()

    # Structure data for ApexCharts
    chart_data = defaultdict(lambda: defaultdict(int))
    for source, day, count in news_by_day:
        domain = urlparse(source).netloc  # Remove https://
        chart_data[domain][day.strftime('%Y-%m-%d')] = count

    return render_template(
        'dashboard.html',
        total_base_urls=total_base_urls,
        total_rss_feeds=total_rss_feeds,
        total_read_feeds=total_read_feeds,
        chart_data=chart_data  # Pass structured data to template
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
    return render_template('login.html', title="Login", form=form)

@app.route('/rssfeeds/add', methods=['GET', 'POST'])
@login_required
def add_rss_feed():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            try:
                # Check if feed already exists for this user
                existing_feed = RSSFeed.query.filter_by(url=url, user_id=current_user.id).first()
                if existing_feed:
                    flash('This RSS feed is already in your list!', 'warning')
                else:
                    # Get favicon URL
                    base_url = '/'.join(url.split('/')[:3])  # Get base domain URL
                    favicon_url = discover_favicon_url(base_url)
                    
                    # Create new feed
                    new_feed = RSSFeed(
                        url=url,
                        user_id=current_user.id,
                        favicon_url=favicon_url
                    )
                    
                    try:
                        db.session.add(new_feed)
                        db.session.commit()
                        flash('RSS feed added successfully!', 'success')
                        
                        # Trigger immediate feed fetch for the new URL
                        with app.app_context():
                            process_feeds(current_user.id)
                            
                    except Exception as e:
                        db.session.rollback()
                        print(f"Database error: {str(e)}")
                        flash('Error saving feed to database', 'error')
                        
            except Exception as e:
                print(f"Error adding feed: {str(e)}")
                flash('Error adding RSS feed. Please check the URL and try again.', 'error')
        else:
            flash('Please enter a URL', 'warning')

    # Get user feeds with additional information, ordered by newest first
    user_feeds = db.session.query(
        RSSFeed,
        db.func.count(RSSFeedContent.id).label('post_count'),
        db.func.max(RSSFeedContent.created_at).label('last_update')
    ).outerjoin(
        RSSFeedContent, 
        RSSFeed.url == RSSFeedContent.feed_base_url
    ).filter(
        RSSFeed.user_id == current_user.id
    ).group_by(
        RSSFeed.id
    ).order_by(RSSFeed.id.desc())\
    .all()

    return render_template('add_rss_feed.html', user_feeds=user_feeds)

@app.route('/rssfeeds/delete/<int:feed_id>', methods=['POST'])
@login_required
def delete_rss_feed(feed_id):
    try:
        feed = RSSFeed.query.get_or_404(feed_id)
        
        # Check if the feed belongs to the current user
        if feed.user_id != current_user.id:
            flash('Unauthorized to delete this feed.', 'error')
            return redirect(url_for('add_rss_feed'))
        
        # First delete all related content
        RSSFeedContent.query.filter_by(feed_base_url=feed.url).delete()
        
        # Then delete the feed itself
        db.session.delete(feed)
        db.session.commit()
        
        flash('RSS feed deleted successfully!', 'success')
    except Exception as e:
        print(f"Error deleting feed: {str(e)}")
        db.session.rollback()
        flash('Error deleting RSS feed.', 'error')
    
    return redirect(url_for('add_rss_feed'))

@app.route('/rssfeeds')
@login_required
def rssfeeds():
    try:
        # Get user's feed URLs
        user_feeds = RSSFeed.query.filter_by(user_id=current_user.id).all()
        user_feed_urls = [feed.url for feed in user_feeds]
        
        # Get posts from user's feeds with proper ordering
        posts = RSSFeedContent.query\
            .filter(RSSFeedContent.feed_base_url.in_(user_feed_urls))\
            .order_by(RSSFeedContent.post_date.desc())\
            .all()
            
        print(f"Found {len(posts)} posts for user {current_user.id}")
        
        return render_template('rssfeeds.html', posts=posts)
    except Exception as e:
        print(f"Error fetching RSS feeds: {str(e)}")
        flash('Error loading RSS feeds', 'error')
        return render_template('rssfeeds.html', posts=[])

@app.route('/rssfeeds/api', methods=['GET'])
@login_required
def get_rss_feeds():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        print(f"🟢 API Called for Page {page}")

        # Get user's feeds
        user_feeds = db.session.query(RSSFeed.url, RSSFeed.favicon_url).filter_by(user_id=current_user.id).all()
        feed_url_to_favicon = {feed.url: feed.favicon_url for feed in user_feeds}

        # Pagination Query
        posts_query = db.session.query(RSSFeedContent).filter(
            RSSFeedContent.feed_base_url.in_(feed_url_to_favicon.keys())
        ).order_by(RSSFeedContent.post_date.desc())

        total_posts = posts_query.count()
        posts = posts_query.offset((page - 1) * per_page).limit(per_page).all()

        print(f"🟢 API Response (Page {page}): {[post.id for post in posts]}") 

        # Return Unique Posts
        posts_data = [
            {
                "id": post.id,
                "title": post.post_title,
                "content": post.post_content,
                "image_url": post.post_featured_image_url or "/static/assets/img/default-placeholder.png",
                "post_date": post.post_date.strftime('%Y-%m-%d %H:%M:%S'),
                "url": post.post_url,
                "base_url": post.feed_base_url.replace("https://", "").replace("http://", ""),
                "favicon_url": feed_url_to_favicon.get(post.feed_base_url, "/static/assets/img/favicon.png"),
            }
            for post in posts
        ]

        return jsonify({
            "has_more": (page * per_page) < total_posts,
            "posts": posts_data,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/rssfeeds/log', methods=['POST'])
@login_required
def log_read():
    """Log when a user clicks on a post."""
    try:
        data = request.get_json()
        rss_feed_content_url = data.get('rss_feed_content_url')

        if not rss_feed_content_url:
            return jsonify({"error": "Invalid rss_feed_content_url"}), 400

        new_log = ReadLog(user_id=current_user.id, rss_feed_content_url=rss_feed_content_url)
        db.session.add(new_log)
        db.session.commit()

        return jsonify({"message": "Read log created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_gravatar_url(email, size=100):
    """Generate a Gravatar URL based on the user's email."""
    if not email:
        return "https://www.gravatar.com/avatar/?d=identicon&s={}".format(size)

    email_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"

app.jinja_env.globals.update(get_gravatar_url=get_gravatar_url)

@app.route('/rssfeeds/fetch', methods=['POST'])
@login_required
def fetch_feeds_route():
    """Manually trigger RSS feed updates."""
    try:
        fetch_rss_feed_updates()
        return jsonify({"message": "RSS feeds updated successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Start scheduler after Flask app initialization
run_scheduler()

# Add this after your app initialization
@app.cli.command("fix-feed-urls")
def fix_feed_urls_command():
    """Fix existing feed base URLs in the database."""
    with app.app_context():
        fix_existing_feed_base_urls()

# If you want to run it immediately after startup
with app.app_context():
    fix_existing_feed_base_urls()

def is_valid_public_url(url):
    """
    Validate if a URL is safe to make requests to.
    Prevents SSRF by checking for private IPs and invalid domains.
    """
    try:
        # Parse URL
        parsed = urlparse(url)
        
        # Check URL scheme
        if parsed.scheme not in ['http', 'https']:
            return False
            
        # Extract domain
        domain = parsed.netloc.split(':')[0]
        
        # Validate domain format
        if not domain or '.' not in domain:
            return False
            
        # Check for valid TLD
        ext = tldextract.extract(url)
        if not ext.suffix:
            return False

        # Resolve domain to IP
        try:
            ip_addresses = socket.getaddrinfo(domain, None)
        except socket.gaierror:
            return False

        # Check each resolved IP
        for addr in ip_addresses:
            ip_str = addr[4][0]
            ip = ipaddress.ip_address(ip_str)
            
            # Check if IP is private
            if (ip.is_private or ip.is_loopback or 
                ip.is_link_local or ip.is_multicast or 
                ip.is_reserved or ip.is_unspecified):
                return False

        # URL length check
        if len(url) > 2048:
            return False

        # Check for allowed characters
        allowed_chars = set('abcdefghijklmnopqrstuvwxyz'
                          'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                          '0123456789-._~:/?#[]@!$&\'()*+,;=')
        if not all(c in allowed_chars for c in url):
            return False

        return True
    except Exception:
        return False

def safe_request(url, method='GET', headers=None, timeout=10):
    """
    Make a safe HTTP request that prevents SSRF.
    """
    if not is_valid_public_url(url):
        raise ValueError("Invalid or unsafe URL")

    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    if headers:
        default_headers.update(headers)

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=default_headers,
            timeout=timeout,
            allow_redirects=True,
            verify=True  # Verify SSL certificates
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Request failed: {str(e)}")

@app.route('/check_new_articles')
@login_required
def check_new_articles():
    try:
        # Get and validate the timestamp
        last_check_time = request.args.get('lastCheck')
        try:
            last_check_time = float(last_check_time)
            if not (0 <= last_check_time <= datetime.now().timestamp()):
                raise ValueError("Invalid timestamp")
        except (TypeError, ValueError):
            return jsonify({'hasNewArticles': False, 'error': 'Invalid timestamp'}), 400

        # Get user's feeds with proper query parameters
        user_feeds = RSSFeed.query\
            .filter_by(user_id=current_user.id)\
            .all()

        feed_urls = []
        for feed in user_feeds:
            if is_valid_public_url(feed.url):
                feed_urls.append(feed.url)

        # Use parameterized query
        newer_articles = RSSFeedContent.query\
            .filter(RSSFeedContent.feed_base_url.in_(feed_urls))\
            .filter(RSSFeedContent.created_at > datetime.fromtimestamp(last_check_time))\
            .first()

        return jsonify({
            'hasNewArticles': newer_articles is not None,
            'timestamp': datetime.now().timestamp()
        })

    except Exception as e:
        app.logger.error(f"Error checking for new articles: {str(e)}")
        return jsonify({'hasNewArticles': False, 'error': 'Internal server error'}), 500

def get_featured_image(entry, feed_url):
    """Extract featured image from a feed entry with multiple fallback options."""
    print(f"\nAttempting to extract image for entry: {entry.get('title', 'Untitled')}")
    
    try:
        # 1. Try media_content
        if hasattr(entry, 'media_content'):
            print("Checking media_content...")
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    url = media.get('url')
                    print(f"Found media_content image: {url}")
                    return url

        # 2. Try media_thumbnail
        if hasattr(entry, 'media_thumbnail'):
            print("Checking media_thumbnail...")
            for media in entry.media_thumbnail:
                if media.get('url'):
                    url = media.get('url')
                    print(f"Found media_thumbnail image: {url}")
                    return url

        # 3. Try enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            print("Checking enclosures...")
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    url = enclosure.get('href')
                    print(f"Found enclosure image: {url}")
                    return url

        # 4. Try content
        print("Checking content...")
        if hasattr(entry, 'content') and entry.content:
            for content_item in entry.content:
                if 'value' in content_item:
                    soup = BeautifulSoup(content_item.value, 'html.parser')
                    # Try to find image in content
                    img = soup.find('img')
                    if img and img.get('src'):
                        url = img.get('src')
                        print(f"Found content image: {url}")
                        return url

        # 5. Try summary
        print("Checking summary...")
        if hasattr(entry, 'summary'):
            soup = BeautifulSoup(entry.summary, 'html.parser')
            img = soup.find('img')
            if img and img.get('src'):
                url = img.get('src')
                print(f"Found summary image: {url}")
                return url

        # 6. Try description
        print("Checking description...")
        if hasattr(entry, 'description'):
            soup = BeautifulSoup(entry.description, 'html.parser')
            img = soup.find('img')
            if img and img.get('src'):
                url = img.get('src')
                print(f"Found description image: {url}")
                return url

        # 7. Try to fetch og:image from the post URL
        if entry.get('link'):
            print(f"Fetching post URL: {entry.link}")
            try:
                response = safe_request(entry.link, timeout=5)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try og:image
                og_image = soup.find('meta', property='og:image') or \
                          soup.find('meta', attrs={'name': 'og:image'}) or \
                          soup.find('meta', attrs={'name': 'twitter:image'})
                if og_image and og_image.get('content'):
                    url = og_image.get('content')
                    print(f"Found og:image: {url}")
                    return url
                
                # Try article:image
                article_image = soup.find('meta', property='article:image')
                if article_image and article_image.get('content'):
                    url = article_image.get('content')
                    print(f"Found article:image: {url}")
                    return url
                
                # Try first image in article
                article = soup.find('article') or soup.find('main') or soup
                if article:
                    img = article.find('img')
                    if img and img.get('src'):
                        url = img.get('src')
                        # Convert relative URLs to absolute
                        if not url.startswith(('http://', 'https://')):
                            url = urljoin(feed_url, url)
                        print(f"Found article image: {url}")
                        return url
                
            except Exception as e:
                print(f"Error fetching post URL: {str(e)}")

        print("No image found in any source")
        return None

    except Exception as e:
        print(f"Error in image extraction: {str(e)}")
        return None

def process_feeds(user_id=None):
    """Process RSS feeds for all users or a specific user."""
    print("🔄 Processing RSS feeds...")
    try:
        feeds_query = RSSFeed.query
        if user_id:
            feeds_query = feeds_query.filter_by(user_id=user_id)
        feeds = feeds_query.all()

        for feed in feeds:
            if not is_valid_public_url(feed.url):
                print(f"⚠️ Skipping invalid feed URL: {feed.url}")
                continue

            try:
                print(f"\nProcessing feed: {feed.url}")
                
                # Try to get the feed content
                response = safe_request(feed.url)
                parsed_feed = feedparser.parse(response.content)

                # Debug feed parsing
                print(f"Feed title: {parsed_feed.feed.get('title', 'Unknown')}")
                print(f"Number of entries: {len(parsed_feed.entries)}")

                if not parsed_feed.entries:
                    print("No entries found in feed")
                    continue

                # Process each entry
                for entry in parsed_feed.entries[:20]:
                    try:
                        print(f"\nProcessing entry: {entry.get('title', 'Untitled')}")
                        
                        # Get featured image with improved extraction
                        post_featured_image_url = get_featured_image(entry, feed.url)
                        
                        if post_featured_image_url:
                            print(f"Successfully extracted image: {post_featured_image_url}")
                        else:
                            print("No image found for this entry")

                        # Check if post already exists
                        existing_post = RSSFeedContent.query.filter_by(
                            feed_base_url=feed.url,
                            post_url=entry.get('link', '')
                        ).first()

                        if not existing_post:
                            new_post = RSSFeedContent(
                                feed_base_url=feed.url,
                                post_title=entry.get('title', 'Untitled')[:255],
                                post_date=get_entry_date(entry),
                                post_content=entry.get('summary', '') or entry.get('description', ''),
                                post_featured_image_url=post_featured_image_url,
                                post_url=entry.get('link', ''),
                                created_at=datetime.utcnow()
                            )
                            db.session.add(new_post)
                            print(f"Added new post: {new_post.post_title}")

                    except Exception as entry_error:
                        print(f"Error processing entry: {str(entry_error)}")
                        continue

                try:
                    db.session.commit()
                    print(f"Successfully processed feed: {feed.url}")
                except Exception as commit_error:
                    print(f"Error committing changes: {str(commit_error)}")
                    db.session.rollback()

            except Exception as feed_error:
                print(f"Error processing feed {feed.url}: {str(feed_error)}")
                db.session.rollback()
                continue

    except Exception as e:
        print(f"Error processing feeds: {str(e)}")
        db.session.rollback()
    finally:
        print("✅ Feed processing completed")

def get_entry_date(entry):
    """Extract date from entry with multiple fallback options."""
    for date_field in ['published', 'updated', 'created']:
        if hasattr(entry, date_field):
            try:
                date_str = getattr(entry, date_field)
                # Try multiple date formats
                for date_format in [
                    '%a, %d %b %Y %H:%M:%S %z',
                    '%Y-%m-%dT%H:%M:%S%z',
                    '%Y-%m-%dT%H:%M:%SZ',
                    '%Y-%m-%d %H:%M:%S',
                ]:
                    try:
                        return datetime.strptime(date_str, date_format)
                    except ValueError:
                        continue
            except:
                continue
    
    return datetime.utcnow()

if __name__ == '__main__':
    app.run(debug=True, port=5090)