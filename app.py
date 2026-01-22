from flask import Flask, jsonify, request
import jwt
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

@app.route('/')
def hello_world():
    return jsonify({'message': 'Hello World!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)