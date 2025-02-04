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
    favicon_url = db.Column(db.String(255), nullable=True)

    # Add cascade deletion for related content
    posts = db.relationship('RSSFeedContent', 
                          backref='feed',
                          cascade='all, delete-orphan',
                          foreign_keys='RSSFeedContent.feed_base_url',
                          primaryjoin='RSSFeed.url == RSSFeedContent.feed_base_url')

    user = db.relationship('User', backref=db.backref('rss_feeds', lazy='dynamic'))

    def __repr__(self):
        return f"<RSSFeed(id={self.id}, url={self.url}, favicon_url={self.favicon_url})>"


# RSSFeedContent Model
class RSSFeedContent(db.Model):
    __tablename__ = 'rss_feed_content'

    id = db.Column(db.Integer, primary_key=True)
    feed_base_url = db.Column(db.String(255), db.ForeignKey('rss_feed.url', ondelete='CASCADE'), nullable=False)
    post_title = db.Column(db.String(255), nullable=False)
    post_date = db.Column(db.DateTime, nullable=True)
    post_content = db.Column(db.Text, nullable=True)
    post_featured_image_url = db.Column(db.String(255), nullable=True)
    post_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<RSSFeedContent(id={self.id}, title={self.post_title})>"


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