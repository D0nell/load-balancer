from flask import Flask, jsonify
import os

app = Flask(__name__)

# Get the container/server name from an environment variable, default to 'Unknown_Server'
SERVER_NAME = os.environ.get('SERVER_ID', 'Unknown_Server')

@app.route('/home', methods=['GET'])
def home():
    return jsonify({
        "message": f"Hello from {SERVER_NAME}",
        "status": "successful"
    }), 200

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    # The load balancer uses this endpoint to check if this server is still healthy
    return "", 200

if __name__ == '__main__':
    # Run the server on port 5000 inside the container
    app.run(host='0.0.0.0', port=5000)