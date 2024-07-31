from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from datetime import datetime
import uuid
import logging
from flask_sqlalchemy import SQLAlchemy
import os
from groq import Groq

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

socketio = SocketIO(app, cors_allowed_origins="*")
logging.basicConfig(level=logging.DEBUG)

active_users = {}

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

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
    flag_reason = db.Column(db.String(500), nullable=True)
    community = db.relationship('Community', back_populates='messages')

    def to_dict(self):
        return {
            'id': self.id,
            'community_id': self.community_id,
            'sender': self.sender,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'flagged': self.flagged,
            'flag_reason': self.flag_reason
        }

def check_message_with_ai(message_content):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an AI moderator of a finance based community chat. Analyze the given message and determine if it's appropriate. If it's inappropriate, explain why. The motive is to stop the span or inappropriate and misleading marketing messages."},
                {"role": "user", "content": f"Please analyze this message:\n\n{message_content}"}
            ],
            model="llama-3.1-70b-versatile",
        )
        
        analysis = chat_completion.choices[0].message.content
        is_flagged = "inappropriate" in analysis.lower() or "not appropriate" in analysis.lower()
        return is_flagged, analysis if is_flagged else None
    except Exception as e:
        print(f"Error calling Groq API: {str(e)}")
        return False, None

@app.route('/api/communities', methods=['POST'])
def create_community():
    data = request.json
    new_community = Community(
        name=data['name'],
        description=data['description'],
        tags=','.join(data['tags']),
        moderator=data['moderator'],
        chat_room=str(uuid.uuid4())
    )
    db.session.add(new_community)
    db.session.commit()
    return jsonify(new_community.to_dict()), 201

@app.route('/api/communities', methods=['GET'])
def get_communities():
    communities = Community.query.all()
    return jsonify([community.to_dict() for community in communities])

@app.route('/api/communities/<int:community_id>', methods=['GET'])
def get_community(community_id):
    community = Community.query.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    return jsonify(community.to_dict())

@app.route('/api/communities/<int:community_id>/join', methods=['POST'])
def join_community(community_id):
    data = request.json
    community = Community.query.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    
    if data['userId'] not in community.members.split(','):
        community.members += f",{data['userId']}" if community.members else data['userId']
        db.session.commit()
    return jsonify({"message": "User joined community"}), 200

@app.route('/api/communities/<int:community_id>/leave', methods=['POST'])
def leave_community(community_id):
    data = request.json
    community = Community.query.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    
    if community.moderator == data['userId']:
        return jsonify({"error": "Moderator cannot leave the community"}), 400
    
    members = community.members.split(',')
    if data['userId'] in members:
        members.remove(data['userId'])
        community.members = ','.join(members)
        db.session.commit()
    return jsonify({"message": "User left community"}), 200

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    user = active_users.pop(request.sid, None)
    if user:
        community = Community.query.get(user["community_id"])
        if community:
            leave_room(community.chat_room)
            emit('user_left', {"username": user["username"]}, room=community.chat_room)

@socketio.on('join')
def on_join(data):
    username = data['username']
    community_id = data['communityId']
    community = Community.query.get(community_id)
    if not community:
        emit('error', {"message": "Community not found"})
        return
    
    join_room(community.chat_room)
    active_users[request.sid] = {"username": username, "community_id": community_id}
    emit('user_joined', {"username": username}, room=community.chat_room)

@socketio.on('leave')
def on_leave(data):
    user = active_users.get(request.sid)
    if user:
        community = Community.query.get(user["community_id"])
        if community:
            leave_room(community.chat_room)
            emit('user_left', {"username": user["username"]}, room=community.chat_room)
        active_users.pop(request.sid)

@socketio.on('message')
def handle_message(data):
    user = active_users.get(request.sid)
    if not user:
        emit('error', {"message": "User not found"})
        return
    
    community = Community.query.get(user["community_id"])
    if not community:
        emit('error', {"message": "Community not found"})
        return
    
    is_flagged, flag_reason = check_message_with_ai(data['message'])
    
    new_message = Message(
        sender=user["username"],
        content=data['message'],
        community_id=community.id,
        flagged=is_flagged,
        flag_reason=flag_reason
    )
    db.session.add(new_message)
    db.session.commit()
    
    emit('message', {
        "sender": user["username"],
        "content": data['message'],
        "timestamp": new_message.timestamp.isoformat(),
        "flagged": is_flagged,
        "flag_reason": flag_reason
    }, room=community.chat_room)

    if is_flagged:
        emit('flagged_message', {
            "message_id": new_message.id,
            "sender": user["username"],
            "content": data['message'],
            "timestamp": new_message.timestamp.isoformat(),
            "flag_reason": flag_reason
        }, room=community.chat_room)

@app.route('/api/communities/<int:community_id>/messages', methods=['GET'])
def get_messages(community_id):
    community = Community.query.get(community_id)
    if not community:
        return jsonify({"error": "Community not found"}), 404
    
    messages = Message.query.filter_by(community_id=community_id).order_by(Message.timestamp.asc()).all()
    return jsonify([message.to_dict() for message in messages])

@socketio.on_error_default
def default_error_handler(e):
    print(f"An error occurred: {str(e)}")
    emit('error', {'message': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)