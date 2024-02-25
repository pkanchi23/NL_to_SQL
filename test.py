# Streamlit user interface
import streamlit as st
import sqlite3
import pandas as pd
import os
from pathlib import Path
import openai
import promptlayer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Connect to your SQL database
# Adjust this line to match your database type and credentials
current_dir = Path(__file__).parent
db_path = current_dir / 'northwind.db'
feedback_data_path = str(current_dir/"feedback_data.csv")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

#setup the dataframe
df = pd.read_csv(feedback_data_path)
df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

# Get details of the 'Orders' table
cursor.execute("PRAGMA table_info(Orders)")
columns = cursor.fetchall()

# Extract column names from the rows
column_names = [column[1] for column in columns]  # column[1] contains the name of the column

# Fetch one row of example data from the 'Orders' table
cursor.execute("SELECT * FROM Orders LIMIT 1")
example_data = cursor.fetchone()

# Pair each column name with the corresponding example data
column_data_pairs = [f"{column_names[i]}: {example_data[i]}" for i in range(len(column_names))]

# Concatenate the column-data pairs into a single string, separated by new lines
column_data_string = "\n".join(column_data_pairs)





st.title("SQL Query Generator Example To Fix Buttons")

natural_language_input = st.text_input("Enter your question:", "How many different ship names are there?")

def save_feedback(natural_language_input, sql_query, feedback):
    current_dir = Path(__file__).parent
    feedback_data_path = str(current_dir/"feedback_data.csv")
    #setup the dataframe
    df = pd.read_csv(feedback_data_path)
    new_row = {
            "Natural Language Question": natural_language_input, 
            "Returned SQL": sql_query, 
            "Feedback": feedback
        }
    df = df.append(new_row, ignore_index=True)
    print("should have worked?")
    df.to_csv(feedback_data_path, index=False)
    

if st.button("Generate SQL Query", key="submit"):
    sql_query = "SELECT * FROM ORDERS"
    st.text(f"SQL Query: {sql_query}")
    st.session_state['initial_button_pressed'] = True
    # Execute the SQL query
    try:
        df = pd.read_sql_query(sql_query, conn)
        #Replace the sample of the original database with the result of the SQL query
        # st.session_state.display_sample = False  #Update session state to stop displaying the sample
        st.write(df)  #Display the result of the SQL query
    except Exception as e:
        st.error(f"Error executing query: {e}")
    
    # Initialize session state for feedback if it doesn't exist
    if 'user_feedback' not in st.session_state:
        st.session_state['user_feedback'] = ""
    
if 'initial_button_pressed' not in st.session_state:
    st.session_state['initial_button_pressed'] = False

if st.session_state['initial_button_pressed']:
    #code rating
    st.write("Rate your result:")
    # Creating two columns next to each other with minimal spacing
    thumbs_up, thumbs_down, _, _, _,_, _, _, _, _, _, _, _,_, _ = st.columns(15)
    feedback = ""
    if thumbs_up.button("👍", key="thumbs_up"):
        st.session_state['user_feedback'] = "Positive"
        save_feedback(natural_language_input, sql_query, "Positive")
        st.write("Positive feedback clicked")
        st.success("You clicked 👍")

    if thumbs_down.button("👎", key="thumbs_down"):
        st.session_state['user_feedback'] = "Negative"
        save_feedback(natural_language_input, sql_query, "Negative")
        st.write("Negative feedback clicked")
        st.error("You clicked 👎")

# Close the connection to the database at the end of the app's execution
conn.close()
