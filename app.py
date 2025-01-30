import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from models import db, User, RSSFeed, RSSFeedContent, ReadLog
from rssfeedparser import process_feeds
from forms import RegistrationForm, LoginForm
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from urllib.parse import urlparse
import hashlib

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'another_strong_key_here_supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'mysql+pymysql://rss_db_user:rssdbuserpassword@localhost/rss_db'
)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Scheduler setup
scheduler = BackgroundScheduler()

# Function to fetch and process feeds
def fetch_rss_feed_updates():
    """Fetch RSS feed updates for all users."""
    with app.app_context():
        try:
            print("Fetching RSS feeds for all users...")
            process_feeds(None)  # Process feeds for all users
            print("RSS feeds processed successfully!")
        except Exception as e:
            print(f"Error during RSS feed update: {e}")

from bs4 import BeautifulSoup
import requests

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

# Add scheduler job to fetch RSS feeds every 2 minutes
if not scheduler.get_jobs():
    scheduler.add_job(func=fetch_rss_feed_updates, trigger="interval", minutes=2, id="rss_feed_job")
    print("Scheduler job added successfully.")

# Start the scheduler
scheduler.start()
print("Scheduler started successfully.")

# Ensure tables are created when the app context is initialized
with app.app_context():
    db.create_all()

# Clean shutdown of scheduler
@app.teardown_appcontext
def shutdown_scheduler(exception=None):
    """Cleanly shut down the scheduler."""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            print("Scheduler shut down successfully.")
    except Exception as e:
        print(f"Error shutting down scheduler: {e}")

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

    # Fetch base RSS URLs count
    total_base_urls = db.session.query(RSSFeedContent.feed_base_url).distinct().count()

    # Fetch available RSS feeds count
    total_rss_feeds = RSSFeedContent.query.count()

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
        rss_url = request.form.get('url')
        user_id = current_user.id

        if rss_url:
            existing_feed = RSSFeed.query.filter_by(url=rss_url, user_id=user_id).first()
            if existing_feed:
                flash('You have already added this RSS feed.', 'warning')
            else:
                # Extract base URL for favicon discovery
                base_url = rss_url.split('/')[0] + '//' + rss_url.split('/')[2]
                favicon_url = discover_favicon_url(base_url)

                new_feed = RSSFeed(url=rss_url, user_id=user_id, favicon_url=favicon_url)
                try:
                    db.session.add(new_feed)
                    db.session.commit()
                    flash('RSS Feed added successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error adding feed: {e}', 'danger')
        else:
            flash('Please provide a valid RSS URL.', 'danger')

    user_feeds = RSSFeed.query.filter_by(user_id=current_user.id).all()
    return render_template('add_rss_feed.html', user_feeds=user_feeds)

@app.route('/rssfeeds/delete/<int:feed_id>', methods=['POST'])
@login_required
def delete_rss_feed(feed_id):
    """Delete an RSS feed."""
    feed = db.session.get(RSSFeed, feed_id)
    if not feed or feed.user_id != current_user.id:
        flash("You don't have permission to delete this feed.", 'danger')
        return redirect(url_for('add_rss_feed'))
    db.session.delete(feed)
    db.session.commit()
    flash('RSS Feed deleted successfully!', 'success')
    return redirect(url_for('add_rss_feed'))

@app.route('/rssfeeds', methods=['GET'])
@login_required
def rssfeeds():
    """Render RSS Feeds template."""
    return render_template('rssfeeds.html')

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

if __name__ == '__main__':
    app.run(debug=True, port=5090)