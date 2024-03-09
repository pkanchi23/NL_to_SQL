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
    payload = request.get_json()
    data = payload.get('data', {}) 
    sql_query = data.get('NL to SQL')
    if isinstance(sql_query, dict):
        sql_query = sql_query.get('value')
    else:
        sql_query = sql_query
    
    if not sql_query:
        return jsonify({'error': 'No SQL_query provided'}), 400

    try:
        conn = get_db_connection()
        df = pd.read_sql_query(sql_query, conn)
        df = df.head(50)
        conn.close()
        return jsonify(df.to_dict(orient='records'))
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
