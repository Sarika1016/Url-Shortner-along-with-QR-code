from flask import Flask, request, render_template, redirect, url_for, jsonify, send_from_directory
import random
import string
import qrcode
import os
import hashlib
from flask_cors import CORS
from urllib.parse import urlparse
import re

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024  # 16KB max request size
app.config['ALLOWED_HOSTS'] = ['localhost', '127.0.0.1']  # Add your production domain
app.config['QR_CODE_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'qr_codes')

# Dictionary to store short URLs
db = {}

# Ensure directories exist
os.makedirs(app.config['QR_CODE_DIR'], exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'), exist_ok=True)

# Constants
SHORT_URL_LENGTH = 6
ALIAS_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_ALIAS_LENGTH = 32

def generate_short_url():
    """Generate a random short URL."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=SHORT_URL_LENGTH))

def is_valid_url(url):
    """Validate URL format and security."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except:
        return False

def sanitize_input(input_str):
    """Sanitize user input."""
    return input_str.strip()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorten', methods=['POST'])
def shorten_url():
    try:
        original_url = sanitize_input(request.form.get('url', ''))
        alias = sanitize_input(request.form.get('alias', ''))

        if not original_url:
            return jsonify({"error": "URL is required"}), 400

        if not is_valid_url(original_url):
            return jsonify({"error": "Invalid URL format. Please include http:// or https://"}), 400

        if alias:
            if len(alias) > MAX_ALIAS_LENGTH:
                return jsonify({"error": f"Alias must be less than {MAX_ALIAS_LENGTH} characters"}), 400
            if not ALIAS_PATTERN.match(alias):
                return jsonify({"error": "Alias can only contain letters, numbers, hyphens, and underscores"}), 400
            if alias in db:
                return jsonify({"error": "Alias already taken"}), 400
            short_url = alias
        else:
            short_url = generate_short_url()
            while short_url in db:
                short_url = generate_short_url()

        db[short_url] = original_url
        return jsonify({"short_url": request.host_url + short_url})

    except Exception as e:
        app.logger.error(f"Error in shorten_url: {str(e)}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/<short_url>')
def redirect_url(short_url):
    if short_url in db:
        return redirect(db[short_url])
    return "URL not found", 404

@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    try:
        data = request.get_json(force=True)
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"error": "No URL provided"}), 400

        if not is_valid_url(url):
            return jsonify({"error": "Invalid URL format"}), 400

        # Generate a unique filename for the QR code
        url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
        qr_filename = f"{url_hash}.png"
        qr_path = os.path.join(app.config['QR_CODE_DIR'], qr_filename)

        print(f"QR code path: {qr_path}")  # Debug print
        print(f"Directory exists: {os.path.exists(app.config['QR_CODE_DIR'])}")  # Debug print
        print(f"Directory is writable: {os.access(app.config['QR_CODE_DIR'], os.W_OK)}")  # Debug print

        # Generate QR code if it doesn't exist
        if not os.path.exists(qr_path):
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')
            img.save(qr_path)
            print(f"QR code saved: {os.path.exists(qr_path)}")  # Debug print

        # Return the URL to the QR code image
        qr_url = url_for('static', filename=f'qr_codes/{qr_filename}', _external=True)
        print(f"QR code URL: {qr_url}")  # Debug print
        return jsonify({"qr_code": qr_url})

    except Exception as e:
        app.logger.error(f"Error in generate_qr: {str(e)}")
        return jsonify({"error": f"An internal error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
