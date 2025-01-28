from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# User Model
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Hashed password
    is_active = db.Column(db.Boolean, default=True)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


# RSSFeed Model
class RSSFeed(db.Model):
    __tablename__ = 'rss_feed'

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    favicon_url = db.Column(db.String(255), nullable=True)  # Column for storing favicon URL

    user = db.relationship('User', backref=db.backref('rss_feeds', lazy='dynamic'))

    def __repr__(self):
        return f"<RSSFeed(id={self.id}, url={self.url}, favicon_url={self.favicon_url})>"


# RSSFeedContent Model
class RSSFeedContent(db.Model):
    __tablename__ = 'rss_feed_content'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    feed_base_url = db.Column(db.String(255), nullable=False)  # The base URL of the RSS feed
    post_title = db.Column(db.String(255), nullable=False)  # Title of the RSS post
    post_date = db.Column(db.DateTime, nullable=True)  # Published date of the post
    post_content = db.Column(db.Text, nullable=True)  # Content or summary of the post
    post_featured_image_url = db.Column(db.String(500), nullable=True)  # Featured image URL of the post
    post_url = db.Column(db.String(500), nullable=False)  # URL of the post
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Record creation timestamp
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Record update timestamp

    def __repr__(self):
        return f"<RSSFeedContent(id={self.id}, feed_base_url={self.feed_base_url}, post_title={self.post_title[:30]}, post_url={self.post_url})>"


# ReadLog Model
class ReadLog(db.Model):
    __tablename__ = 'rss_read_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rss_feed_content_url = db.Column(db.String(500), nullable=False)  # Updated column
    read_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='rss_read_logs', lazy=True)

    def __repr__(self):
        return f"<ReadLog user_id={self.user_id}, rss_feed_content_url={self.rss_feed_content_url}, read_at={self.read_at}>"