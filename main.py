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

# Assuming environment variables are already set
promptlayer.api_key = os.environ.get('PROMPTLAYER_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY
promptlayer.openai.api_key = OPENAI_API_KEY

# Function to refine SQL query using PromptLayer
def refine_sql_with_promptlayer(natural_language, columns):

    variables = {
    'database_name':"Northwest Traders database from Microsoft 2016",
    'columns':"",
    'other_considerations':columns,
    'User_NL': natural_language
    }

    NL_to_SQL_template = promptlayer.templates.get("NL_to_SQL", {
        "provider": "openai",
        "input_variables": variables
    })          
    
    response, pl_id = promptlayer.openai.ChatCompletion.create(
        **NL_to_SQL_template["llm_kwargs"],
        model='gpt-3.5-turbo',
        temperature=0.7,
        max_tokens=150,
        return_pl_id=True
    )
    
    # Associate request to Prompt Template
    promptlayer.track.prompt(request_id=pl_id, 
        prompt_name='NL_to_SQL', prompt_input_variables=variables)

    # Evaluate the request
#     score = evaluate_request(resp)
#     print(score)
#     promptlayer.track.score(request_id=pl_id, score=score)
    
    refined_sql = response.choices[0].message.content.strip()
    return refined_sql

# Connect to your SQL database
# Adjust this line to match your database type and credentials
conn = sqlite3.connect('/Users/pranav/Desktop/NYU_Stuff/Projects/northwind.db')
cursor = conn.cursor()

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

st.title("SQL Query Generator Example")

# Display a sample of the original database
if 'display_sample' not in st.session_state or st.session_state.display_sample:
    sample_query = "SELECT * FROM Orders"  # Example: Adjust table name and limit as needed
    sample_df = pd.read_sql_query(sample_query, conn)
    st.write("Original Database:", sample_df)

natural_language_input = st.text_input("Enter your question:", "How many different ship names are there?")

if st.button("Generate SQL Query"):
    # Assuming convert_to_sql function returns a valid SQL query as a string
    # sql_query = convert_to_sql(natural_language_input)
    sql_query = refine_sql_with_promptlayer(natural_language_input, column_data_string)
    st.text(f"SQL Query: {sql_query}")
    
    # Execute the SQL query
    try:
        df = pd.read_sql_query(sql_query, conn)
        #Replace the sample of the original database with the result of the SQL query
        # st.session_state.display_sample = False  #Update session state to stop displaying the sample
        st.write(df)  #Display the result of the SQL query
    except Exception as e:
        st.error(f"Error executing query: {e}")
    # Add thumbs up/down buttons and ask the user to rate the result
    st.write("Rate your result:")
    col1, col2 = st.columns(2)
    if col1.button("👍", key="thumbs_up"):
        st.session_state['user_feedback'] = "positive"
        print("Result worked?")
    if col2.button("👎", key="thumbs_down"):
        st.session_state['user_feedback'] = "negative"
        print("Result didn't work.")

# Close the connection to the database at the end of the app's execution
conn.close()
