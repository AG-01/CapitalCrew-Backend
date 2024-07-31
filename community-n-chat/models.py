from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    tags = db.Column(db.String(255), nullable=False)
    moderator = db.Column(db.String(100), nullable=False)
    chat_room = db.Column(db.String(100), nullable=False)
    members = db.Column(db.String(255), nullable=True)
    messages = db.relationship('Message', back_populates='community')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'tags': self.tags.split(','),
            'moderator': self.moderator,
            'chat_room': self.chat_room,
            'members': self.members.split(',') if self.members else []
        }

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey('community.id'), nullable=False)
    sender = db.Column(db.String(100), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    flagged = db.Column(db.Boolean, default=False)
    community = db.relationship('Community', back_populates='messages')

    def to_dict(self):
        return {
            'id': self.id,
            'community_id': self.community_id,
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'flagged': self.flagged
        }