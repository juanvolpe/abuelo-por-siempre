from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import csv
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add debug prints for directory paths
DATA_DIR = '/data' if os.path.exists('/data') else os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(DATA_DIR, 'static')

print(f"DATA_DIR is: {DATA_DIR}")
print(f"STATIC_DIR is: {STATIC_DIR}")
print(f"Static directory exists: {os.path.exists(STATIC_DIR)}")

print("Checking data directory...")
print(f"Does /data exist? {os.path.exists('/data')}")
print(f"Current directory contents: {os.listdir('/')}")
if os.path.exists('/data'):
    print(f"Data directory contents: {os.listdir('/data')}")

# Set up data directory for persistent storage
DATA_DIR = '/data' if os.path.exists('/data') else os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(DATA_DIR, 'csv')
STATIC_DIR = os.path.join(DATA_DIR, 'static')
IMAGES_DIR = os.path.join(STATIC_DIR, 'images')

# Enhanced directory creation with logging
def ensure_directories():
    directories = [
        DATA_DIR,
        CSV_DIR,
        STATIC_DIR,
        IMAGES_DIR
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")  # Add explicit print for debugging
        except Exception as e:
            print(f"Error creating directory {directory}: {str(e)}")

# Call this function before Flask app setup
ensure_directories()

# Create symbolic link for static/images if we're on Render
if os.path.exists('/data'):
    static_images_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images')
    if not os.path.exists(static_images_path):
        os.makedirs(os.path.dirname(static_images_path), exist_ok=True)
        if os.path.exists(static_images_path):
            os.remove(static_images_path)
        os.symlink(IMAGES_DIR, static_images_path)

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "X-Requested-With", "Accept", "Origin"]
}})

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATA_DIR, "names.db")}'
app.config['UPLOAD_FOLDER'] = IMAGES_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Add route to serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

db = SQLAlchemy(app)

# File paths
DATA_CSV = os.path.join(CSV_DIR, 'data.csv')
CALENDAR_NOTES_CSV = os.path.join(CSV_DIR, 'calendar_notes.csv')
MOOD_TRACKER_CSV = os.path.join(CSV_DIR, 'mood_tracker.csv')

# Update init_csv_files() with logging
def init_csv_files():
    csv_files = {
        DATA_CSV: ['first_name', 'last_name', 'image_path'],
        CALENDAR_NOTES_CSV: ['date', 'note'],
        MOOD_TRACKER_CSV: ['date', 'name', 'score', 'message']
    }
    
    for file_path, headers in csv_files.items():
        try:
            if not os.path.exists(file_path):
                logger.info(f"Creating CSV file: {file_path}")
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
            else:
                logger.info(f"CSV file exists: {file_path}")
        except Exception as e:
            logger.error(f"Error with CSV file {file_path}: {str(e)}")

init_csv_files()

# OpenAI Configuration
from openai import OpenAI
api_key = os.getenv('OPENAI_API_KEY')
print(f"OpenAI API Key configured: {'Yes' if api_key else 'No'}")  # Debug log

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "cursortest1990@gmail.com"
SENDER_PASSWORD = os.getenv('EMAIL_APP_PASSWORD')
RECIPIENT_EMAIL = "cursortest1990@gmail.com"

def load_family_context():
    context = []
    if os.path.exists(DATA_CSV):
        with open(DATA_CSV, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            family_members = [f"{row['first_name']} {row['last_name']}" for row in reader]
            if family_members:
                context.append("Family members I know: " + ", ".join(family_members))
    return "\n".join(context)

SYSTEM_PROMPT = f"""You are a loving and wise grandfather (abuelo) named Cosi who has lived a long, rich life full of experiences. 

Your personality traits and background:
- You are warm, patient, and always speak with kindness
- You often mix Spanish and English in your responses
- You love sharing stories from your past experiences
- You have a great sense of humor and occasionally tell dad jokes
- You're knowledgeable about traditional recipes and family traditions
- You care deeply about family values and giving good advice

Family Context:
{load_family_context()}

When responding:
1. Always start with a warm greeting in Spanish if it's a new conversation
2. Use endearing terms like "mi amor", "mi hij@", "querid@"
3. Share relevant life experiences or stories when appropriate
4. Include some Spanish phrases naturally in your responses
5. Keep your tone gentle and supportive
6. If asked about recipes or traditions, share detailed explanations
7. End your responses with encouraging words or wisdom
8. If asked about family members, refer to the ones you know from the context

Remember to:
- Keep responses relatively concise (2-3 paragraphs maximum)
- Be empathetic and understanding
- Share wisdom in a non-preachy way
- Use simple language that everyone can understand
- Always maintain a positive and supportive tone"""

# Store conversation history
conversations = {}

def load_calendar_notes():
    if os.path.exists(CALENDAR_NOTES_CSV):
        notes = {}
        with open(CALENDAR_NOTES_CSV, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    if row['note'].startswith('{'):
                        notes[row['date']] = json.loads(row['note'].replace("'", '"'))
                    else:
                        notes[row['date']] = {'text': row['note']}
                except Exception as e:
                    notes[row['date']] = {'text': row['note']}
        return notes
    return {}

def save_calendar_notes(notes):
    with open(CALENDAR_NOTES_CSV, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['date', 'note'])
        writer.writeheader()
        for date, note in notes.items():
            if isinstance(note, dict):
                writer.writerow({'date': date, 'note': json.dumps(note)})
            else:
                writer.writerow({'date': date, 'note': json.dumps({'text': str(note)})})

def send_mood_notification(name, score, message, date):
    try:
        print(f"Attempting to send email notification for {name}")
        print(f"Using SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"Sender email: {SENDER_EMAIL}")
        print(f"Password available: {'Yes' if SENDER_PASSWORD else 'No'}")
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f"Mood Alert: {name} is feeling down"

        body = f"""
        Dear Family Member,

        {name} has recorded a low mood score today.

        Date: {date}
        Mood Score: {score}/5
        Message: {message}

        It might be a good time to reach out and show some support.

        Best regards,
        Abuelo por siempre
        """

        msg.attach(MIMEText(body, 'plain'))
        print("Message created successfully")

        print("Connecting to SMTP server...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        print("Starting TLS...")
        server.starttls()
        print("Attempting login...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        print("Login successful, sending message...")
        server.send_message(msg)
        print("Message sent successfully")
        server.quit()
        print("SMTP connection closed")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

@app.route('/')
def home():
    return render_template('calendar.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/calendar/notes', methods=['GET'])
def get_calendar_notes():
    notes = load_calendar_notes()
    return jsonify(notes)

@app.route('/calendar/notes', methods=['POST'])
def save_note():
    try:
        data = request.json
        date = data.get('date')
        note = data.get('note')
        
        if not date:
            return jsonify({'error': 'Date is required'}), 400
            
        notes = load_calendar_notes()
        
        if note:
            if not isinstance(note, dict):
                note = {'text': str(note), 'images': []}
            if 'images' not in note:
                note['images'] = []
            if 'text' not in note:
                note['text'] = ''
            
            if date in notes and isinstance(notes[date], dict) and 'images' in notes[date]:
                note['images'] = notes[date]['images']
            
            notes[date] = note
        elif date in notes:
            del notes[date]
            
        save_calendar_notes(notes)
        return jsonify({'message': 'Note saved successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to save note'}), 500
@app.route('/calendar/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    date = request.form.get('date')
    
    if not file or not date:
        return jsonify({'error': 'Invalid request'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{date}_{int(time.time())}_{file.filename}")
        
        # Save to the images directory inside static
        filepath = os.path.join(IMAGES_DIR, filename)
        try:
            file.save(filepath)
            print(f"Saved image to: {filepath}")  # Debug print
            
            # Use relative path for URL
            image_url = f"/static/images/{filename}"
            
            notes = load_calendar_notes()
            if date not in notes:
                notes[date] = {'text': '', 'images': []}
            elif isinstance(notes[date], str):
                notes[date] = {'text': notes[date], 'images': []}
            
            if 'images' not in notes[date]:
                notes[date]['images'] = []
            
            notes[date]['images'].append(image_url)
            save_calendar_notes(notes)
            
            return jsonify({'image_url': image_url})
        except Exception as e:
            print(f"Error saving image: {str(e)}")  # Debug print
            return jsonify({'error': f'Failed to save image: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/calendar/remove-image', methods=['POST'])
def remove_image():
    data = request.get_json()
    date = data.get('date')
    index = data.get('index')
    
    if not date or index is None:
        return jsonify({'error': 'Invalid request'}), 400
    
    notes = load_calendar_notes()
    if date in notes and isinstance(notes[date], dict) and 'images' in notes[date]:
        try:
            image_url = notes[date]['images'][index]
            if image_url.startswith('/static/'):
                image_url = image_url[1:]  # Remove leading slash
            
            image_path = os.path.join(os.path.dirname(__file__), image_url)
            if os.path.exists(image_path):
                os.remove(image_path)
            
            notes[date]['images'].pop(index)
            save_calendar_notes(notes)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Image not found'}), 404

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic', 'heif'}  # Added HEIC/HEIF support
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/quick-check/save', methods=['POST'])
def save_quick_check():
    try:
        data = request.get_json()
        date = data.get('date')
        name = data.get('name')
        score = data.get('score')
        message = data.get('message', '')

        if not all([date, name, score]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        mood_data = {}
        if os.path.exists(MOOD_TRACKER_CSV):
            with open(MOOD_TRACKER_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mood_data[row['date']] = row

        mood_data[date] = {
            'date': date,
            'name': name,
            'score': score,
            'message': message
        }

        with open(MOOD_TRACKER_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'name', 'score', 'message'])
            writer.writeheader()
            for entry in mood_data.values():
                writer.writerow(entry)

        if int(score) <= 2:
            send_mood_notification(name, score, message, date)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/quick-check/data/<date>')
def get_quick_check_data(date):
    try:
        if os.path.exists(MOOD_TRACKER_CSV):
            with open(MOOD_TRACKER_CSV, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['date'] == date:
                        return jsonify({
                            'date': row['date'],
                            'name': row['name'],
                            'score': int(row['score']),
                            'message': row['message']
                        })
        return jsonify({})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        print("\n=== Chat Request Started ===")
        print(f"OpenAI API Key configured: {'Yes' if api_key else 'No'}")
        print(f"OpenAI API Key: {api_key[:10]}... (first 10 chars)")
        
        if not api_key:
            print("OpenAI API key is not set")
            return jsonify({
                'error': 'OpenAI API key not configured',
                'response': 'Lo siento, I am not able to chat right now. Please ask the administrator to configure the API key.'
            }), 500

        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = request.headers.get('X-Session-ID', 'default')
        
        print(f"Received message: '{user_message}'")
        print(f"Session ID: {session_id}")

        if session_id not in conversations:
            print("Creating new conversation for session")
            conversations[session_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

        conversations[session_id].append({"role": "user", "content": user_message})
        print(f"Current conversation length: {len(conversations[session_id])}")

        try:
            print("\nSending request to OpenAI API...")
            print("Request details:")
            print(f"- Model: gpt-3.5-turbo")
            print(f"- Max tokens: 150")
            print(f"- Temperature: 0.7")
            
            # Create a clean client instance
            client = OpenAI()  # Let it use the environment variable directly
            
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=conversations[session_id],
                max_tokens=150,
                temperature=0.7
            )
            print("Received response from OpenAI API")

            bot_response = completion.choices[0].message.content.strip()
            print(f"Bot response: '{bot_response[:50]}...'")
            
            conversations[session_id].append({"role": "assistant", "content": bot_response})
            print("=== Chat Request Completed ===\n")
            return jsonify({'response': bot_response})

        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            print("=== Chat Request Failed ===\n")
            return jsonify({
                'error': 'OpenAI API error',
                'response': f'Lo siento, I am having trouble thinking right now. Error: {str(e)}'
            }), 500

    except Exception as e:
        print(f"General error in chat route: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print("=== Chat Request Failed ===\n")
        return jsonify({
            'error': 'Failed to process message',
            'response': f'Lo siento, I had trouble understanding that. Error: {str(e)}'
        }), 500

@app.route('/test-directories')
def test_directories():
    try:
        dirs = {
            'DATA_DIR': {'path': DATA_DIR, 'exists': os.path.exists(DATA_DIR), 'contents': os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else []},
            'STATIC_DIR': {'path': STATIC_DIR, 'exists': os.path.exists(STATIC_DIR), 'contents': os.listdir(STATIC_DIR) if os.path.exists(STATIC_DIR) else []},
            'IMAGES_DIR': {'path': IMAGES_DIR, 'exists': os.path.exists(IMAGES_DIR), 'contents': os.listdir(IMAGES_DIR) if os.path.exists(IMAGES_DIR) else []}
        }
        return jsonify(dirs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True) 