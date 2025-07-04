import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATA_FILE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/screenshots.json')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['DATA_FILE']), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def load_screenshots():
    try:
        if os.path.exists(app.config['DATA_FILE']):
            with open(app.config['DATA_FILE'], 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def save_screenshots(data):
    try:
        temp_file = app.config['DATA_FILE'] + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Atomic write operation
        if os.path.exists(temp_file):
            os.replace(temp_file, app.config['DATA_FILE'])
            return True
        return False
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/screenshots', methods=['GET'])
def get_screenshots():
    sort_by = request.args.get('sort', 'recent')
    screenshots = load_screenshots()
    
    if sort_by == 'likes':
        screenshots.sort(key=lambda x: x.get('likes', 0), reverse=True)
    elif sort_by == 'oldest':
        screenshots.sort(key=lambda x: x.get('created_at', ''))
    else:
        screenshots.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return jsonify(screenshots)

@app.route('/api/screenshots', methods=['POST'])
def add_screenshot():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        new_screenshot = {
            'id': str(datetime.now().timestamp()),
            'title': request.form.get('title', 'Untitled'),
            'url': request.form.get('url', ''),
            'image': f"/static/uploads/{filename}",
            'notes': request.form.get('notes', ''),
            'likes': 0,
            'liked': False,
            'saved': False,
            'created_at': datetime.now().isoformat()
        }
        
        screenshots = load_screenshots()
        screenshots.append(new_screenshot)
        
        if save_screenshots(screenshots):
            return jsonify(new_screenshot), 201
        else:
            return jsonify({'error': 'Failed to save data'}), 500
            
    except Exception as e:
        print(f"Error in add_screenshot: {e}")
        return jsonify({'error': str(e)}), 500

# ... rest of your routes ...

if __name__ == '__main__':
    app.run(debug=True)