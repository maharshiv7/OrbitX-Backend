from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

# 🟢 1. App Initialization (Sirf EK baar)
app = Flask(__name__)
CORS(app)

# ==========================================
# 🔐 DATABASE CONNECTION (AIVEN LIVE MySQL)
# ==========================================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="mysql-143c29e-maharshiv7.i.aivencloud.com", 
            port=17981,
            user="avnadmin",
            password="AVNS_tnqk4Z0AZgczhFrQhr4",
            database="defaultdb",
            ssl_disabled=False  # Aiven requires SSL
        )
        return conn
    except mysql.connector.Error as err:
        print(f"❌ DB Connection Failed: {err}")
        return None

# ==========================================
# 🏗️ AUTO-CREATE TABLES FOR FRESH DATABASE
# ==========================================
def create_tables():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Create Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(100) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Create Bookmarks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    planet_name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_bookmark (username, planet_name)
                )
            """)
            conn.commit()
            print("✅ Database Tables Verified/Created on Aiven!")
        except mysql.connector.Error as err:
            print(f"❌ Table Creation Failed: {err}")
        finally:
            conn.close()

# Run table creation on startup
create_tables()

# ==========================================
# 🌌 EXOPLANET DATABASE ENGINE
# ==========================================
exoplanet_db = []

def load_exoplanet_data():
    global exoplanet_db
    print("Fetching massive Exoplanet Data from NASA... Please wait.")
    try:
        url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+pl_name,sy_dist,pl_rade,disc_year+from+ps+where+default_flag=1&format=json"        
        response = requests.get(url, timeout=15)
        response.raise_for_status() 
        raw_data = response.json()
        
        for planet in raw_data:
            if planet.get('sy_dist') is not None and planet.get('pl_rade') is not None:
                exoplanet_db.append({
                    "name": planet['pl_name'],
                    "distance_ly": round(planet['sy_dist'] * 3.262, 2),
                    "radius_earth": round(planet['pl_rade'], 2),
                    "year": planet.get('disc_year', 'Unknown') 
                })
        print(f"✅ Success! {len(exoplanet_db)} Exoplanets loaded from NASA.")
        
    except Exception as e:
        print(f"❌ NASA API Failed: {e}")
        print("⚠️ Loading OrbitX Offline Backup Database...")
        # Fallback backup database
        exoplanet_db.extend([
            {"name": "Proxima Centauri b", "distance_ly": 4.24, "radius_earth": 1.03, "year": 2016},
            {"name": "TRAPPIST-1 e", "distance_ly": 39.46, "radius_earth": 0.92, "year": 2017},
            {"name": "Kepler-452 b", "distance_ly": 1799.0, "radius_earth": 1.63, "year": 2015}
        ])

# Data load karein
load_exoplanet_data()

# ==========================================
# 🛡️ AUTHENTICATION ROUTES
# ==========================================
@app.route('/')
def home():
    return "<h1>🚀 OrbitX Backend Engine is LIVE and Running!</h1>"

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username, email, password = data.get('username'), data.get('email'), data.get('password')
    
    if not all([username, email, password]):
        return jsonify({"status": "error", "message": "All fields are required!"})

    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Database server down!"})
    
    try:
        cursor = conn.cursor()
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", (username, email, hashed_pw))
        conn.commit()
        return jsonify({"status": "success", "message": "User registered successfully!"})
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": "Username/Email already exists or DB Error!"})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email, password = data.get('email'), data.get('password')
    
    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Database server down!"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            return jsonify({"status": "success", "username": user['username'], "message": "Welcome back!"})
        return jsonify({"status": "error", "message": "Invalid Email or Password!"})
    finally:
        conn.close()

# ==========================================
# 🔭 OTHER UTILITY ROUTES
# ==========================================

@app.route('/api/exoplanets')
def filter_exoplanets():
    max_distance = float(request.args.get('max_dist', 10000))
    max_size = float(request.args.get('max_size', 100))
    filtered = [p for p in exoplanet_db if p['distance_ly'] <= max_distance and p['radius_earth'] <= max_size]
    return jsonify({"status": "success", "total_matches": len(filtered), "data": sorted(filtered, key=lambda x: x['distance_ly'])[:50]})

@app.route('/api/iss-location')
def get_iss_location():
    try:
        data = requests.get("http://api.open-notify.org/iss-now.json").json()
        return jsonify({"status": "success", "latitude": data['iss_position']['latitude'], "longitude": data['iss_position']['longitude']})
    except:
        return jsonify({"status": "error"})
    
@app.route('/api/iss-predict')
def predict_iss_location():
    try:
        target_time = request.args.get('timestamp')
        if not target_time:
            return jsonify({"status": "error", "message": "Time nahi mila bhai!"})
        
        url = f"https://api.wheretheiss.at/v1/satellites/25544/positions?timestamps={target_time}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        return jsonify({
            "status": "success",
            "latitude": data[0]['latitude'],
            "longitude": data[0]['longitude'],
            "timestamp": target_time
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ==========================================
# ⭐ BOOKMARK (FAVORITES) ROUTES
# ==========================================

@app.route('/api/save_bookmark', methods=['POST'])
def save_bookmark():
    data = request.json
    username = data.get('username')
    planet_name = data.get('planet_name')

    if not username or not planet_name:
        return jsonify({"status": "error", "message": "Missing data!"})

    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Database server down!"})
    
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bookmarks (username, planet_name) VALUES (%s, %s)", (username, planet_name))
        conn.commit()
        return jsonify({"status": "success", "message": f"{planet_name} added to your Universe!"})
    except mysql.connector.IntegrityError:
        return jsonify({"status": "error", "message": "Already saved in your Universe!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        conn.close()

@app.route('/api/my_bookmarks', methods=['POST'])
def my_bookmarks():
    data = request.json
    username = data.get('username')

    conn = get_db_connection()
    if not conn: return jsonify({"status": "error", "message": "Database server down!"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT planet_name FROM bookmarks WHERE username = %s", (username,))
        saved_planets = cursor.fetchall()
        
        planet_names = [p['planet_name'] for p in saved_planets]
        return jsonify({"status": "success", "data": planet_names})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    finally:
        conn.close()

# ==========================================
# 🕵️‍♂️ CLASSIFIED FILES ROUTE
# ==========================================
@app.route('/api/classified')
def get_classified_files():
    secret_files = [
        {
            "id": "wow-signal",
            "title": "INCIDENT 1977: THE WOW! SIGNAL",
            "status": "UNSOLVED",
            "statusClass": "status-yellow",
            "date": "August 15, 1977",
            "origin": "Sagittarius Constellation",
            "content": """
                <p>On August 15, 1977, the Big Ear radio telescope intercepted a strong narrowband radio signal. It lasted for exactly 72 seconds. The astronomer on duty, Jerry R. Ehman, was so shocked that he wrote "Wow!" on the computer printout.</p>
                <p>The signal originated from <span class="redacted">empty space</span> in the constellation Sagittarius. Despite decades of searching, the signal has <span class="redacted">never repeated</span>.</p>
                <p><strong>ANALYSIS:</strong> The frequency was 1420.4056 MHz. This is the hydrogen line—the exact frequency that <span class="redacted">intelligent alien life</span> would logically use to communicate across the universe.</p>
                <p>Current Status: We are still listening. Something is out there.</p>
            """
        },
        {
            "id": "oumuamua",
            "title": "OBJECT: 'OUMUAMUA",
            "status": "CLASSIFIED",
            "statusClass": "status-red",
            "date": "October 19, 2017",
            "origin": "Interstellar Space (Vega)",
            "content": """
                <p>The first interstellar object detected passing through our Solar System. Officially classified as a comet, but its behavior defies known astrophysics.</p>
                <p>As 'Oumuamua left our solar system, it suddenly <span class="redacted">accelerated</span> without emitting any gas or dust, violating gravity models. NASA officially denies it, but internal theories suggest it was an <span class="redacted">extraterrestrial solar sail</span> or a probe sent to map our system.</p>
                <p><strong>NOTE:</strong> Trajectory suggests it came from the direction of Vega. By the time we pointed our advanced telescopes at it, it had already begun transmitting <span class="redacted">[DATA EXPUNGED]</span>.</p>
            """
        },
        {
            "id": "great-attractor",
            "title": "ANOMALY: THE GREAT ATTRACTOR",
            "status": "CRITICAL",
            "statusClass": "status-red",
            "date": "Ongoing",
            "origin": "Zone of Avoidance",
            "content": """
                <p>Our Milky Way galaxy is moving at 600 kilometers per second towards a massive, unseen region of space known as The Great Attractor.</p>
                <p>It possesses the mass of tens of thousands of galaxies. The problem? It is located in the "Zone of Avoidance," obscured by our own galaxy's dust. We cannot see what is pulling us.</p>
                <p>Recent deep-space infrared scans revealed <span class="redacted">massive structures</span> pulling entire superclusters towards a central point. Theories range from a super-massive black hole to a <span class="redacted">rip in the fabric of spacetime</span>.</p>
                <p>We are being pulled into the dark.</p>
            """
        }
    ]
    return jsonify({"status": "success", "data": secret_files})

if __name__ == '__main__':
    app.run(debug=True, port=5000)