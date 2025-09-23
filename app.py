from flask import Flask, render_template, send_from_directory, request, jsonify, session, redirect, url_for
import os
import json
import random
import base64
import time
from datetime import datetime
from functools import wraps
from collections import deque
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3NoHeaderError, APIC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'javier_radio_secret_key_2024')

# Data files
VISITOR_COUNT_FILE = 'visitor_count.txt'
SONG_DATA_FILE = 'song_data.json'

# Activity tracking
recent_activities = deque(maxlen=100)
RATINGS_DATA_FILE = 'ratings_data.json'


# Admin configuration
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Initialize data files
def initialize_data_files():
    """Initialize data files if they don't exist"""
    if not os.path.exists(VISITOR_COUNT_FILE):
        with open(VISITOR_COUNT_FILE, 'w') as f:
            f.write('0')

    if not os.path.exists(SONG_DATA_FILE):
        with open(SONG_DATA_FILE, 'w') as f:
            json.dump({}, f)

    if not os.path.exists(RATINGS_DATA_FILE):
        with open(RATINGS_DATA_FILE, 'w') as f:
            json.dump({}, f)


@app.template_filter('timestamp_to_date')
def timestamp_to_date_filter(timestamp):
    try:
        if isinstance(timestamp, str) and timestamp.replace('.', '').isdigit():
            timestamp = float(timestamp)
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return 'Unknown date'



initialize_data_files()

# Rating management functions
def load_ratings_data():
    """Load ratings data from JSON file"""
    try:
        with open(RATINGS_DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_ratings_data(ratings_data):
    """Save ratings data to JSON file"""
    try:
        with open(RATINGS_DATA_FILE, 'w') as f:
            json.dump(ratings_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving ratings data: {e}")
        return False

def add_song_rating(song_key, rating, user_id=None):
    """Add a rating for a song"""
    ratings_data = load_ratings_data()

    if song_key not in ratings_data:
        ratings_data[song_key] = {
            'ratings': [],
            'total_ratings': 0,
            'average_rating': 0.0
        }

    # Use IP-based user identification if no user_id provided
    if user_id is None:
        user_id = request.remote_addr if request else 'anonymous'

    # Check if user has already rated this song
    existing_rating = None
    for i, rating_entry in enumerate(ratings_data[song_key]['ratings']):
        if rating_entry['user_id'] == user_id:
            existing_rating = i
            break

    rating_entry = {
        'user_id': user_id,
        'rating': int(rating),
        'timestamp': datetime.now().timestamp()
    }

    if existing_rating is not None:
        # Update existing rating
        ratings_data[song_key]['ratings'][existing_rating] = rating_entry
    else:
        # Add new rating
        ratings_data[song_key]['ratings'].append(rating_entry)

    # Recalculate average
    ratings_list = [r['rating'] for r in ratings_data[song_key]['ratings']]
    ratings_data[song_key]['total_ratings'] = len(ratings_list)
    ratings_data[song_key]['average_rating'] = sum(ratings_list) / len(ratings_list) if ratings_list else 0.0

    save_ratings_data(ratings_data)
    return ratings_data[song_key]

def get_song_rating_info(song_key):
    """Get rating information for a specific song"""
    ratings_data = load_ratings_data()
    if song_key in ratings_data:
        return ratings_data[song_key]
    return {
        'ratings': [],
        'total_ratings': 0,
        'average_rating': 0.0
    }

def get_user_rating(song_key, user_id=None):
    """Get a specific user's rating for a song"""
    if user_id is None:
        user_id = request.remote_addr if request else 'anonymous'

    ratings_data = load_ratings_data()
    if song_key in ratings_data:
        for rating_entry in ratings_data[song_key]['ratings']:
            if rating_entry['user_id'] == user_id:
                return rating_entry['rating']
    return 0

# Template filters
@app.template_filter('timestamp_to_date')
def timestamp_to_date_filter(timestamp):
    try:
        if isinstance(timestamp, str) and timestamp.replace('.', '').isdigit():
            timestamp = float(timestamp)
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return 'Unknown date'

# Visitor counter functions
def get_visitor_count():
    try:
        if os.path.exists(VISITOR_COUNT_FILE):
            with open(VISITOR_COUNT_FILE, 'r') as f:
                content = f.read().strip()
                return int(content) if content.isdigit() else 0
        return 0
    except Exception as e:
        print(f"Error reading visitor count: {e}")
        return 0

def increment_visitor_count():
    try:
        count = get_visitor_count()
        count += 1
        with open(VISITOR_COUNT_FILE, 'w') as f:
            f.write(str(count))
        return count
    except Exception as e:
        print(f"Error incrementing visitor count: {e}")
        return get_visitor_count()

# Song management functions
def get_song_duration(filepath):
    """Get duration of an MP3 file in seconds"""
    if not MUTAGEN_AVAILABLE:
        return 180  # Default 3 minutes if mutagen not available
    try:
        audio = MP3(filepath)
        return int(audio.info.length)
    except:
        return 180

def extract_album_art(filepath):
    """Extract album art from MP3 file and return as base64 encoded string"""
    if not MUTAGEN_AVAILABLE:
        return None
    try:
        audio = MP3(filepath)
        if audio.tags:
            for tag in audio.tags.values():
                if hasattr(tag, 'type') and tag.type == 3:  # Front cover
                    # Encode image data as base64
                    image_data = base64.b64encode(tag.data).decode('utf-8')
                    # Get mime type
                    mime_type = tag.mime
                    return f"data:{mime_type};base64,{image_data}"
        return None
    except Exception as e:
        print(f"Error extracting album art from {filepath}: {e}")
        return None

def load_song_data():
    """Load song data from JSON file"""
    try:
        if os.path.exists(SONG_DATA_FILE):
            with open(SONG_DATA_FILE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        return {}
    except Exception as e:
        print(f"Error loading song data: {e}")
        return {}

def save_song_data(data):
    """Save song data to JSON file"""
    try:
        with open(SONG_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving song data: {e}")

def initialize_song_data():
    """Initialize song data for all MP3 files in javiradio directory"""
    songs = {}
    javiradio_dir = os.path.join('static', 'javiradio')

    if os.path.exists(javiradio_dir):
        for filename in os.listdir(javiradio_dir):
            if filename.endswith('.mp3'):
                key = filename.replace('.mp3', '').replace(' ', '_').lower()
                filepath = os.path.join(javiradio_dir, filename)

                # Extract album art
                album_art = extract_album_art(filepath)

                songs[key] = {
                    'title': filename.replace('.mp3', ''),
                    'artist': 'JaviRadio',
                    'filename': filename,
                    'duration': get_song_duration(filepath),
                    'play_count': 0,
                    'total_listen_time': 0,
                    'album_art': album_art
                }

    existing_data = load_song_data()
    for key, song in songs.items():
        if key in existing_data:
            song['play_count'] = existing_data[key].get('play_count', 0)
            song['total_listen_time'] = existing_data[key].get('total_listen_time', 0)
            # Keep existing album art if available, otherwise use newly extracted
            if 'album_art' in existing_data[key] and existing_data[key]['album_art']:
                song['album_art'] = existing_data[key]['album_art']

    save_song_data(songs)
    return songs



# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    """Main JaviRadio page"""
    visitor_count = increment_visitor_count()
    initialize_song_data()
    return render_template('index.html', visitor_count=visitor_count)

@app.route('/shae')
def shae_page():
    """Simple romantic message page"""
    return render_template('shae.html')

@app.route('/api/songs')
def get_songs():
    """Get list of all songs"""
    try:
        songs = load_song_data()
        if not songs:
            songs = initialize_song_data()

        song_list = []
        for key, song in songs.items():
            # Validate required fields
            if not all(field in song for field in ['title', 'duration', 'play_count', 'filename']):
                continue

            # Get rating information for this song
            rating_info = get_song_rating_info(key)

            song_list.append({
                'key': key,
                'title': song['title'],
                'artist': song.get('artist', 'JaviRadio Collection'),
                'duration': int(song['duration']) if song['duration'] else 0,
                'play_count': int(song['play_count']) if song['play_count'] else 0,
                'formatted_duration': f"{int(song['duration'])//60}:{int(song['duration'])%60:02d}" if song['duration'] else "0:00",
                'url': f"/static/javiradio/{song['filename']}",
                'average_rating': float(round(rating_info['average_rating'], 1)),
                'total_ratings': rating_info['total_ratings'],
                'album_art': song.get('album_art', None)
            })

        return jsonify(song_list)
    except Exception as e:
        print(f"Error loading songs: {e}")
        return jsonify([])

@app.route('/api/play/<song_key>')
def play_song(song_key):
    """Play a song and increment play count"""
    try:
        songs = load_song_data()

        if song_key in songs:
            songs[song_key]['play_count'] += 1
            save_song_data(songs)

            # Track activity
            add_activity(song_key, songs[song_key]['title'])

            return jsonify({
                'success': True,
                'song': songs[song_key],
                'play_count': songs[song_key]['play_count']
            })

        return jsonify({'success': False, 'error': 'Song not found'}), 404
    except Exception as e:
        print(f"Error playing song {song_key}: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/stats')
def get_stats():
    """Get radio statistics"""
    try:
        songs = load_song_data()
        ratings_data = load_ratings_data()

        total_plays = sum(int(song.get('play_count', 0)) for song in songs.values())
        total_listen_time = sum(int(song.get('total_listen_time', 0)) for song in songs.values())

        # Calculate rating statistics
        total_ratings = 0
        total_rating_sum = 0
        rated_songs = 0

        for song_key in songs.keys():
            if song_key in ratings_data:
                song_ratings = ratings_data[song_key]
                if song_ratings['total_ratings'] > 0:
                    total_ratings += song_ratings['total_ratings']
                    total_rating_sum += song_ratings['average_rating'] * song_ratings['total_ratings']
                    rated_songs += 1

        overall_average_rating = (total_rating_sum / total_ratings) if total_ratings > 0 else 0

        # Get top songs
        song_list = [(k, v) for k, v in songs.items()]
        song_list.sort(key=lambda x: int(x[1].get('play_count', 0)), reverse=True)
        top_songs = [{'title': v.get('title', k), 'plays': int(v.get('play_count', 0))} for k, v in song_list[:5]]

        # Format listen time
        hours = total_listen_time // 3600
        minutes = (total_listen_time % 3600) // 60
        if hours > 0:
            formatted_listen_time = f"{hours}h {minutes}m"
        else:
            formatted_listen_time = f"{minutes}m"

        return jsonify({
            'total_songs': len(songs),
            'total_plays': total_plays,
            'total_listen_time': total_listen_time,
            'formatted_listen_time': formatted_listen_time,
            'top_songs': top_songs,
            'current_listeners': 1,  # Placeholder for live listeners
            'total_ratings': total_ratings,
            'rated_songs': rated_songs,
            'overall_average_rating': round(overall_average_rating, 1)
        })
    except Exception as e:
        print(f"Error loading stats: {e}")
        return jsonify({
            'total_songs': 0,
            'total_plays': 0,
            'total_listen_time': 0,
            'formatted_listen_time': '0m',
            'top_songs': [],
            'current_listeners': 0,
            'total_ratings': 0,
            'rated_songs': 0,
            'overall_average_rating': 0.0
        })

@app.route('/api/visitor-count')
def get_visitor_count_api():
    """Get current visitor count"""
    try:
        return jsonify({'count': get_visitor_count()})
    except Exception as e:
        print(f"Error getting visitor count: {e}")
        return jsonify({'count': 0})


@app.route('/api/rate/<song_key>', methods=['POST'])
def rate_song(song_key):
    """Submit a rating for a song"""
    try:
        # Validate song exists
        songs = load_song_data()
        if song_key not in songs:
            return jsonify({'error': f'Song "{song_key}" not found'}), 404

        # Validate JSON request
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400

        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Invalid JSON data'}), 400

        rating = data.get('rating')

        # Validate rating value
        if rating is None:
            return jsonify({'error': 'Rating is required'}), 400

        if not isinstance(rating, (int, float)):
            return jsonify({'error': 'Rating must be a number'}), 400

        rating = int(rating)  # Convert to int

        if rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be between 1 and 5 stars'}), 400

        # Add the rating
        rating_info = add_song_rating(song_key, rating)

        return jsonify({
            'success': True,
            'rating_info': rating_info,
            'message': f'Rating of {rating} stars submitted successfully!',
            'song_title': songs[song_key].get('title', song_key)
        })

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        print(f"Error submitting rating for {song_key}: {e}")
        return jsonify({'error': 'Internal server error while submitting rating'}), 500

@app.route('/api/rating/<song_key>')
def get_song_rating(song_key):
    """Get rating information for a specific song"""
    try:
        # Validate song exists (optional check, return zeros if not found)
        songs = load_song_data()
        song_exists = song_key in songs

        if not song_exists:
            return jsonify({
                'song_key': song_key,
                'average_rating': 0.0,
                'total_ratings': 0,
                'user_rating': 0,
                'error': 'Song not found'
            }), 404

        rating_info = get_song_rating_info(song_key)
        user_rating = get_user_rating(song_key)

        return jsonify({
            'song_key': song_key,
            'average_rating': float(round(rating_info['average_rating'], 1)),
            'total_ratings': rating_info['total_ratings'],
            'user_rating': user_rating,
            'song_title': songs[song_key].get('title', song_key)
        })

    except Exception as e:
        print(f"Error getting song rating for {song_key}: {e}")
        return jsonify({
            'song_key': song_key,
            'average_rating': 0.0,
            'total_ratings': 0,
            'user_rating': 0,
            'error': 'Failed to load rating data'
        }), 500

@app.route('/api/ratings')
def get_all_ratings():
    """Get rating information for all songs"""
    try:
        ratings_data = load_ratings_data()
        songs_data = load_song_data()
        result = {}

        # Include ratings for all songs, even those without ratings yet
        for song_key in songs_data.keys():
            if song_key in ratings_data:
                rating_info = ratings_data[song_key]
                result[song_key] = {
                    'average_rating': float(round(rating_info.get('average_rating', 0), 1)),
                    'total_ratings': rating_info['total_ratings'],
                    'song_title': songs_data[song_key].get('title', song_key)
                }
            else:
                result[song_key] = {
                    'average_rating': 0.0,
                    'total_ratings': 0,
                    'song_title': songs_data[song_key].get('title', song_key)
                }

        return jsonify({
            'ratings': result,
            'total_songs': len(songs_data),
            'rated_songs': len([r for r in result.values() if r['total_ratings'] > 0])
        })

    except Exception as e:
        print(f"Error getting all ratings: {e}")
        return jsonify({
            'ratings': {},
            'total_songs': 0,
            'rated_songs': 0,
            'error': 'Failed to load ratings data'
        }), 500

# Admin routes
@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    """Admin login page"""
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Handle admin login"""
    password = request.form.get('password', '')

    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_login.html', error='Invalid password')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    stats = {
        'pending': 0,
        'approved': 0,
        'rejected': 0,
        'total': 0
    }

    return render_template('admin_dashboard.html', stats=stats)



def get_location_from_ip(ip_address):
    """Get location information from IP address - only real data"""
    try:
        # For localhost/development, return localhost info
        if ip_address in ['127.0.0.1', 'localhost', '::1']:
            return {
                'country': 'LOCAL',
                'country_name': 'Local Machine',
                'region': '',
                'city': 'localhost'
            }

        # In production, you could use a service like ipapi.co
        # Uncomment and configure this for real geolocation:
        # response = requests.get(f'https://ipapi.co/{ip_address}/json/')
        # if response.status_code == 200:
        #     return response.json()

        # For now, return minimal info for non-localhost IPs
        return {
            'country': 'XX',
            'country_name': 'Unknown Location',
            'region': '',
            'city': 'Unknown'
        }

    except Exception as e:
        print(f"Error getting location: {e}")
        return {'country': 'XX', 'country_name': 'Unknown', 'region': '', 'city': 'Unknown'}

def add_activity(song_key, song_title):
    """Add a new activity entry"""
    try:
        ip_address = request.remote_addr or '127.0.0.1'
        location_info = get_location_from_ip(ip_address)

        # Format location string
        location_parts = []
        if location_info.get('city'):
            location_parts.append(location_info['city'])
        if location_info.get('region'):
            location_parts.append(location_info['region'])
        if location_info.get('country_name'):
            location_parts.append(location_info['country_name'])

        location_str = ', '.join(location_parts) if location_parts else 'Unknown Location'

        activity = {
            'timestamp': int(time.time()),
            'song_key': song_key,
            'song_title': song_title,
            'location': location_str,
            'country': location_info.get('country', 'XX'),
            'ip_address': ip_address  # Store for deduplication if needed
        }

        recent_activities.appendleft(activity)

    except Exception as e:
        print(f"Error adding activity: {e}")

@app.route('/api/recent-activity')
def get_recent_activity():
    """Get recent listening activity"""
    try:
        # Convert deque to list for JSON serialization
        activities_list = list(recent_activities)

        # Calculate stats
        active_listeners = len(set(activity['ip_address'] for activity in activities_list[-10:]))  # Last 10 activities
        countries = set(activity['country'] for activity in activities_list)
        total_countries = len(countries)

        return jsonify({
            'activities': activities_list[:20],  # Return last 20 activities
            'active_listeners': active_listeners,
            'total_countries': total_countries
        })

    except Exception as e:
        print(f"Error getting recent activity: {e}")
        return jsonify({
            'activities': [],
            'active_listeners': 0,
            'total_countries': 0
        }), 500

# Static file serving
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True, port=8000)
