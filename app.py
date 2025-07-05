import os
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
import pytz
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATA_FILE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/screenshots.json')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['YOUTUBE_API_KEY'] = os.getenv('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY')
app.config['SEO_ANALYSIS_INTERVAL'] = timedelta(hours=6)  # How often to refresh SEO data

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['DATA_FILE']), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def load_screenshots():
    try:
        if os.path.exists(app.config['DATA_FILE']):
            with open(app.config['DATA_FILE'], 'r') as f:
                data = json.load(f)
                # Ensure each item has SEO data
                for item in data:
                    if 'seo_data' not in item:
                        item['seo_data'] = get_default_seo_data()
                return data
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

def get_default_seo_data():
    return {
        'keywords': [],
        'score': 0,
        'last_analyzed': None,
        'views': 0,
        'engagement_rate': 0,
        'ctr': 0,
        'impressions': 0,
        'tags': [],
        'suggested_keywords': []
    }

def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    query = urlparse(url)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
        if query.path.startswith('/embed/'):
            return query.path.split('/')[2]
        if query.path.startswith('/v/'):
            return query.path.split('/')[2]
    return None

def fetch_youtube_data(video_id):
    """Fetch YouTube video data using API"""
    if not app.config['YOUTUBE_API_KEY']:
        return None
        
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={video_id}&key={app.config['YOUTUBE_API_KEY']}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                return data['items'][0]
        return None
    except Exception as e:
        print(f"Error fetching YouTube data: {e}")
        return None

def analyze_seo(video_url, title, description):
    """Analyze SEO for a YouTube video"""
    video_id = extract_video_id(video_url)
    yt_data = fetch_youtube_data(video_id) if video_id else None
    
    # Basic keyword extraction
    keywords = extract_keywords(title + " " + description)
    
    # Calculate basic SEO score (simplified example)
    seo_score = calculate_seo_score(title, description, keywords, yt_data)
    
    seo_data = {
        'keywords': keywords[:10],
        'score': seo_score,
        'last_analyzed': datetime.now(pytz.utc).isoformat(),
        'views': yt_data['statistics']['viewCount'] if yt_data and 'statistics' in yt_data else 0,
        'engagement_rate': calculate_engagement_rate(yt_data) if yt_data else 0,
        'ctr': 0,  # Would need YouTube Analytics API for real CTR
        'impressions': 0,  # Would need YouTube Analytics API
        'tags': yt_data['snippet']['tags'] if yt_data and 'tags' in yt_data['snippet'] else [],
        'suggested_keywords': generate_suggested_keywords(keywords)
    }
    
    return seo_data

def extract_keywords(text):
    """Extract keywords from text (simplified example)"""
    # In a real implementation, you'd use NLP or a keyword extraction library
    words = text.lower().split()
    common_words = {'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
    return [word for word in words if word.isalpha() and word not in common_words][:15]

def calculate_seo_score(title, description, keywords, yt_data):
    """Calculate a basic SEO score (simplified example)"""
    score = 0
    
    # Title factors
    title_words = title.lower().split()
    score += min(len(title_words), 5) * 2  # Up to 10 points for title length
    
    # Keyword in title
    for keyword in keywords[:3]:
        if keyword in title.lower():
            score += 5
    
    # Description length
    desc_length = len(description.split())
    if desc_length > 200:
        score += 10
    elif desc_length > 100:
        score += 5
    
    # YouTube data factors
    if yt_data:
        if 'tags' in yt_data['snippet'] and len(yt_data['snippet']['tags']) > 5:
            score += 5
        
        if int(yt_data['statistics'].get('commentCount', 0)) > 10:
            score += 5
    
    return min(score, 100)  # Cap at 100

def calculate_engagement_rate(yt_data):
    """Calculate engagement rate (simplified)"""
    if not yt_data or 'statistics' not in yt_data:
        return 0
    
    stats = yt_data['statistics']
    views = int(stats.get('viewCount', 0))
    if views == 0:
        return 0
    
    likes = int(stats.get('likeCount', 0))
    comments = int(stats.get('commentCount', 0))
    
    return (likes + comments) / views * 100

def generate_suggested_keywords(keywords):
    """Generate suggested keywords (simplified example)"""
    # In a real implementation, you'd use YouTube's search suggestions or keyword tools
    suggestions = []
    for kw in keywords[:3]:
        suggestions.extend([f"{kw} tutorial", f"best {kw}", f"{kw} tips"])
    return suggestions[:5]

def needs_seo_update(item):
    """Check if SEO data needs to be updated"""
    if 'seo_data' not in item:
        return True
    
    last_updated = item['seo_data'].get('last_analyzed')
    if not last_updated:
        return True
    
    try:
        last_dt = datetime.fromisoformat(last_updated).replace(tzinfo=pytz.utc)
        return datetime.now(pytz.utc) - last_dt > app.config['SEO_ANALYSIS_INTERVAL']
    except:
        return True

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/screenshots', methods=['GET'])
def get_screenshots():
    sort_by = request.args.get('sort', 'recent')
    screenshots = load_screenshots()
    
    # Update SEO data for items that need it
    updated = False
    for item in screenshots:
        if item.get('url') and needs_seo_update(item):
            try:
                item['seo_data'] = analyze_seo(item['url'], item['title'], item.get('notes', ''))
                updated = True
            except Exception as e:
                print(f"Error updating SEO for {item['id']}: {e}")
    
    if updated:
        save_screenshots(screenshots)
    
    # Sorting options
    if sort_by == 'likes':
        screenshots.sort(key=lambda x: x.get('likes', 0), reverse=True)
    elif sort_by == 'oldest':
        screenshots.sort(key=lambda x: x.get('created_at', ''))
    elif sort_by == 'seo_score':
        screenshots.sort(key=lambda x: x.get('seo_data', {}).get('score', 0), reverse=True)
    elif sort_by == 'views':
        screenshots.sort(key=lambda x: int(x.get('seo_data', {}).get('views', 0)), reverse=True)
    elif sort_by == 'engagement':
        screenshots.sort(key=lambda x: float(x.get('seo_data', {}).get('engagement_rate', 0)), reverse=True)
    else:  # recent
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
        
        video_url = request.form.get('url', '')
        
        new_screenshot = {
            'id': str(datetime.now().timestamp()),
            'title': request.form.get('title', 'Untitled'),
            'url': video_url,
            'image': f"/static/uploads/{filename}",
            'notes': request.form.get('notes', ''),
            'likes': 0,
            'liked': False,
            'saved': False,
            'created_at': datetime.now(pytz.utc).isoformat(),
            'seo_data': analyze_seo(video_url, request.form.get('title', ''), request.form.get('notes', '')) if video_url else get_default_seo_data()
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

@app.route('/api/screenshots/<screenshot_id>', methods=['PUT'])
def update_screenshot(screenshot_id):
    try:
        data = request.get_json()
        screenshots = load_screenshots()
        
        for i, screenshot in enumerate(screenshots):
            if screenshot['id'] == screenshot_id:
                # Update fields
                for key in ['title', 'url', 'notes', 'likes', 'liked', 'saved']:
                    if key in data:
                        screenshots[i][key] = data[key]
                
                # If URL changed, update SEO data
                if 'url' in data and data['url'] != screenshot['url']:
                    screenshots[i]['seo_data'] = analyze_seo(
                        data['url'],
                        data.get('title', screenshot['title']),
                        data.get('notes', screenshot.get('notes', ''))
                    )
                
                if save_screenshots(screenshots):
                    return jsonify(screenshots[i])
                else:
                    return jsonify({'error': 'Failed to save data'}), 500
        
        return jsonify({'error': 'Screenshot not found'}), 404
    except Exception as e:
        print(f"Error in update_screenshot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/screenshots/<screenshot_id>', methods=['DELETE'])
def delete_screenshot(screenshot_id):
    try:
        screenshots = load_screenshots()
        updated_screenshots = [s for s in screenshots if s['id'] != screenshot_id]
        
        if len(updated_screenshots) < len(screenshots):
            if save_screenshots(updated_screenshots):
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Failed to save data'}), 500
        else:
            return jsonify({'error': 'Screenshot not found'}), 404
    except Exception as e:
        print(f"Error in delete_screenshot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/screenshots/<screenshot_id>/seo', methods=['GET'])
def get_seo_data(screenshot_id):
    screenshots = load_screenshots()
    for screenshot in screenshots:
        if screenshot['id'] == screenshot_id:
            if needs_seo_update(screenshot):
                screenshot['seo_data'] = analyze_seo(
                    screenshot['url'],
                    screenshot['title'],
                    screenshot.get('notes', '')
                )
                save_screenshots(screenshots)
            return jsonify(screenshot.get('seo_data', get_default_seo_data()))
    
    return jsonify({'error': 'Screenshot not found'}), 404

@app.route('/api/screenshots/<screenshot_id>/refresh-seo', methods=['POST'])
def refresh_seo_data(screenshot_id):
    screenshots = load_screenshots()
    for i, screenshot in enumerate(screenshots):
        if screenshot['id'] == screenshot_id:
            screenshots[i]['seo_data'] = analyze_seo(
                screenshot['url'],
                screenshot['title'],
                screenshot.get('notes', '')
            )
            if save_screenshots(screenshots):
                return jsonify(screenshots[i]['seo_data'])
            else:
                return jsonify({'error': 'Failed to save data'}), 500
    
    return jsonify({'error': 'Screenshot not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)