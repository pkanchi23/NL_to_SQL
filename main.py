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

    refined_sql = response.choices[0].message.content.strip()
    return refined_sql

#Function to clean the output string of SQL code, was returning in markdown format so this changes that
def clean_string(input_string):
    # Check if the string is encapsulated by triple backticks and contains `sql`
    if input_string.startswith("```sql") and input_string.endswith("```"):
        # Strip the triple backticks and 'sql' identifier from both sides
        cleaned_string = input_string[7:-3].strip()
    elif input_string.startswith("```") and input_string.endswith("```"):
        # If the string starts and ends with triple backticks without 'sql'
        cleaned_string = input_string[3:-3].strip()
    else:
        cleaned_string = input_string
    return cleaned_string

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

st.title("SQL Query Generator Example")

# Display a sample of the original database
if 'display_sample' not in st.session_state or st.session_state.display_sample:
    sample_query = "SELECT * FROM Orders"
    sample_df = pd.read_sql_query(sample_query, conn)
    st.write("Original Database:", sample_df)

natural_language_input = st.text_input("Enter your question:", "How many different ship names are there?")

def save_feedback(natural_language_input, sql_query, feedback, ran):
    current_dir = Path(__file__).parent
    feedback_data_path = str(current_dir/"feedback_data.csv")
    df = pd.read_csv(feedback_data_path)
    new_row = {
            "Natural Language Question": natural_language_input, 
            "Returned SQL": sql_query, 
            "Feedback": feedback,
            "Program Ran": ran
        }
    df = df.append(new_row, ignore_index=True)
    print("should have worked?")
    df.to_csv(feedback_data_path, index=False)


if 'feedback_given' not in st.session_state:
    st.session_state['feedback_given'] = False
if 'SQL_query' not in st.session_state:
    st.session_state['SQL_query'] = ""
if 'program_ran' not in st.session_state:
    st.session_state['program_ran'] = False

if st.button("Generate SQL Query", key="submit"):
    sql_query = refine_sql_with_promptlayer(natural_language_input, column_data_string)
    st.session_state['SQL_query'] = clean_string(sql_query)
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        st.session_state['program_ran'] = True
    except Exception as e:
        st.error(f"Error executing query: {e}")
        st.session_state['program_ran'] = False
    
# Ensure the SQL result remains displayed after feedback
if st.session_state['program_ran']:
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        st.write(df)
    except Exception as e:
        st.error(f"Error re-displaying query result: {e}")
    
if st.session_state['program_ran'] and not st.session_state['feedback_given']:
    st.write("Rate your result:")
    thumbs_up, thumbs_down = st.columns(2)
    if thumbs_up.button("👍", key="thumbs_up"):
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Positive", st.session_state['program_ran'])
        st.success("Thanks for the feedback! 👍")
        st.session_state['feedback_given'] = True
    if thumbs_down.button("👎", key="thumbs_down"):
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Negative", st.session_state['program_ran'])
        st.error("Thanks for the feedback, we're working on improving it!")
        st.session_state['feedback_given'] = True

# Close the connection to the database at the end of the app's execution
conn.close()