from flask import Flask, render_template, request, jsonify  # Flask to create the web server
import sqlite3  # For connecting to the database
import socket  # To get a free port automatically
import webbrowser  # To auto-open the website in a browser
import threading  # To run browser-opening in parallel
import datetime  # To work with date and time

print("✅ Running the correct app.py from vehicle_counter")

# === Initialize the Flask App ===
app = Flask(__name__)

# === Function to Fetch Filtered Vehicle Data ===
def get_data(filter_hour=None, filter_day=None):
    conn = sqlite3.connect("vehicle_data.db")  # Connect to the SQLite database
    cursor = conn.cursor()
    query = "SELECT timestamp, vehicle_type FROM vehicles"  # Base query
    conditions = []  # Used to build WHERE conditions
    params = []  # Values to be passed safely into query

    # If an hour filter is applied, add it to the condition
    if filter_hour:
        conditions.append("strftime('%H', timestamp) = ?")
        params.append(f"{int(filter_hour):02d}")

    # If a day filter is applied (0=Sunday to 6=Saturday)
    if filter_day:
        conditions.append("strftime('%w', timestamp) = ?")
        params.append(str(filter_day))

    # Combine all conditions with AND
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor.execute(query, params)  # Run the final query
    data = cursor.fetchall()  # Get all matching records
    conn.close()  # Close the connection
    return data

# === Route for Web Dashboard (Home Page) ===
@app.route("/")
def index():
    hour = request.args.get("hour")  # Get optional hour filter from URL
    day = request.args.get("day")  # Get optional day filter
    data = get_data(hour, day)  # Get data based on filters

    # Count how many cars, motorcycles, and trucks
    counts = {"car": 0, "motorcycle": 0, "truck": 0}
    for _, v_type in data:
        if v_type in counts:
            counts[v_type] += 1

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Get current time
    return render_template("dashboard.html", data=data, counts=counts, now=now)  # Load HTML template

# === API: Summary Data (Today's and Week's Total + Peak Hour) ===
@app.route("/api/traffic/summary")
def summary_data():
    now = datetime.datetime.now()
    conn = sqlite3.connect("vehicle_data.db")
    cursor = conn.cursor()

    today = now.strftime("%Y-%m-%d")  # Today's date
    week_start = (now - datetime.timedelta(days=now.weekday())).strftime("%Y-%m-%d")  # Start of the week

    summary = {"total_today": 0, "total_week": 0, "peak_hour": 0}

    # Count today's vehicles
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE DATE(timestamp) = ?", (today,))
    summary["total_today"] = cursor.fetchone()[0]

    # Count this week's vehicles
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE DATE(timestamp) >= ?", (week_start,))
    summary["total_week"] = cursor.fetchone()[0]

    # Find the peak hour (most vehicles in 1 hour) today
    cursor.execute("""
        SELECT strftime('%H', timestamp), COUNT(*) FROM vehicles 
        WHERE DATE(timestamp) = ? 
        GROUP BY strftime('%H', timestamp) 
        ORDER BY COUNT(*) DESC LIMIT 1
    """, (today,))
    row = cursor.fetchone()
    summary["peak_hour"] = row[0] if row else "00"  # Default to 00 if no data

    conn.close()
    return jsonify(summary)  # Return as JSON

# === API: Real-Time Count for Current Hour ===
@app.route("/api/traffic/realtime")
def realtime_count():
    now = datetime.datetime.now()
    current_hour = now.strftime("%H")
    today = now.strftime("%Y-%m-%d")

    conn = sqlite3.connect("vehicle_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM vehicles 
        WHERE strftime('%H', timestamp) = ? AND DATE(timestamp) = ?
    """, (current_hour, today))
    count = cursor.fetchone()[0]
    conn.close()

    return jsonify({"current_hour": current_hour, "count": count})

# === API: Hourly Count Breakdown for a Day ===
@app.route("/api/traffic/hourly")
def hourly():
    date = request.args.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))  # Default to today

    conn = sqlite3.connect("vehicle_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%H', timestamp), COUNT(*) FROM vehicles 
        WHERE DATE(timestamp) = ?
        GROUP BY strftime('%H', timestamp)
        ORDER BY strftime('%H', timestamp)
    """, (date,))
    data = cursor.fetchall()
    conn.close()

    return jsonify({int(hour): count for hour, count in data})  # Return hourly breakdown

# === API: Daily Count for Last 7 Days ===
@app.route("/api/traffic/daily")
def daily():
    conn = sqlite3.connect("vehicle_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(timestamp), COUNT(*) FROM vehicles 
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp) DESC LIMIT 7
    """)
    data = cursor.fetchall()
    conn.close()

    return jsonify({day: count for day, count in data})  # Return daily counts as JSON

# === Utility: Find a Free Port to Run the Server ===
def find_free_port():
    s = socket.socket()
    s.bind(('', 0))  # Bind to any free port
    port = s.getsockname()[1]
    s.close()
    return port

# === Utility: Automatically Open the Browser to Show the Dashboard ===
def open_browser(url):
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

# === Start the Flask Server ===
if __name__ == "__main__":
    port = find_free_port()  # Pick an available port
    url = f"http://127.0.0.1:{port}"  # Build the localhost URL
    print(f"\n🚀 Running Dashboard on {url}\n")
    open_browser(url)  # Launch the browser automatically
    app.run(debug=True, use_reloader=False, port=port)  # Start Flask app