from flask import Flask, request, jsonify
import pandas as pd
import sqlite3
from pathlib import Path

app = Flask(__name__)

# Database connection
def get_db_connection():
    current_dir = Path(__file__).parent
    db_path = current_dir / 'northwind.db'
    conn = sqlite3.connect(str(db_path))
    return conn

@app.route('/run-query', methods=['POST'])
def run_query():
    data = request.get_json()
    sql_query = data.get('SQL_query')
    
    if not sql_query:
        return jsonify({'error': 'No SQL_query provided'}), 400

    try:
        conn = get_db_connection()
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
