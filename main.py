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
promptlayer.api_key = os.environ.get('PROMPTLAYER_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY
promptlayer.openai.api_key = OPENAI_API_KEY

# Function to refine SQL query using PromptLayer
def refine_sql_with_promptlayer(natural_language, columns):
    variables = {
    'columns':columns,
    'User_NL': natural_language
    }

    NL_to_SQL_template = promptlayer.templates.get("NL_to_SQL", {
        "provider": "openai",
        "input_variables": variables
    })          
    
    response, pl_id = promptlayer.openai.ChatCompletion.create(
        **NL_to_SQL_template["llm_kwargs"],
        return_pl_id=True
    )
    
    # Associate request to Prompt Template
    promptlayer.track.prompt(request_id=pl_id, 
        prompt_name='NL_to_SQL', prompt_input_variables=variables)

    refined_sql = response.choices[0].message.content
    return refined_sql, pl_id

#convert the SQL response to a natural language answer
def sql_to_NL_answer(df, natural_language):
    df = df.to_string()
    variables = {
    'data':df,
    'question': natural_language
    }

    SQL_to_NL_template = promptlayer.templates.get("SQL to NL", {
        "provider": "openai",
        "input_variables": variables
    })          
    
    response, pl_id = promptlayer.openai.ChatCompletion.create(
        **SQL_to_NL_template["llm_kwargs"],
        return_pl_id=True
    )
    
    # Associate request to Prompt Template
    promptlayer.track.prompt(request_id=pl_id, 
        prompt_name='SQL to NL', prompt_input_variables=variables)

    NL_answer = response.choices[0].message.content
    return NL_answer, pl_id
    
# Connect to your SQL database
current_dir = Path(__file__).parent
db_path = current_dir / 'northwind.db'
feedback_data_path = str(current_dir/"feedback_data.csv")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

#setup the dataframe
df = pd.read_csv(feedback_data_path)
df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

# Get details of the 'Orders' table for column names
cursor.execute("PRAGMA table_info(Orders)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]  # column[1] contains the name of the column

# Pull the first row of data for examples to pass the prompt
cursor.execute("SELECT * FROM Orders LIMIT 1")
example_data = cursor.fetchone()
column_data_pairs = [f"{column_names[i]}: {example_data[i]}" for i in range(len(column_names))]

#Join the data
column_data_string = "\n".join(column_data_pairs)

st.title("SQL Query Generator Example")

# Display a sample of the original database
if 'display_sample' not in st.session_state or st.session_state.display_sample:
    sample_query = "SELECT * FROM Orders"
    sample_df = pd.read_sql_query(sample_query, conn)
    st.write("Original Database:", sample_df)

natural_language_input = st.text_input("Enter your question:", "How many different ship names are there?")

#Push feedback to CSV
def save_feedback(natural_language_input, sql_query, feedback, ran, pl_id):
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
    df.to_csv(feedback_data_path, index=False)
    promptlayer.track.metadata(
        request_id=pl_id,
        metadata={
            "Feedback": feedback,
        }
    )  

#add session state variables to persist in streamlit across runs 
if 'feedback_given' not in st.session_state:
    st.session_state['feedback_given'] = False
if 'SQL_query' not in st.session_state:
    st.session_state['SQL_query'] = ""
if 'program_ran' not in st.session_state:
    st.session_state['program_ran'] = False
if 'pl_id_NL_SQL' not in st.session_state:
    st.session_state['pl_id_NL_SQL'] = None
if 'pl_id_SQL_NL' not in st.session_state:
    st.session_state['pl_id_SQL_NL'] = None


if st.button("Generate SQL Query", key="submit"):
    st.session_state['SQL_query'], pl_id_NL_SQL = refine_sql_with_promptlayer(natural_language_input, column_data_string)
    st.session_state['pl_id_NL_SQL'] = pl_id_NL_SQL
    st.session_state['feedback_given'] = False
    st.session_state['program_ran'] = False
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        st.session_state['program_ran'] = True
        #score 100 if the SQL runs
        promptlayer.track.score(
            request_id=pl_id_NL_SQL,
            score=100
        )
    except Exception as e:
        st.error(f"Error executing query: {e}")
        st.session_state['program_ran'] = False
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Negative", st.session_state['program_ran'])
        #score 0 if the SQL did not run
        promptlayer.track.score(
            request_id=pl_id_NL_SQL,
            score=0
        )
    
# Ensure the SQL result remains displayed after feedback
if st.session_state['program_ran']:
    # st.write("SQL Query: %s" % (st.session_state['SQL_query']))
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        NL_answer, _ = sql_to_NL_answer(df, natural_language_input)
        st.write(df)
        st.write(NL_answer) #NL Answer, could also write out df, to show the selected df
    except Exception as e:
        st.error(f"Error re-displaying query result: {e}")
        st.session_state['program_ran'] = False
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Negative", st.session_state['program_ran'], st.session_state['pl_id_NL_SQL'])
    
feedback_placeholder = st.empty()

#Feedback buttons
if st.session_state['program_ran']:
    st.write("Rate your result:")
    thumbs_up, thumbs_down = st.columns(2)
    if thumbs_up.button("👍", key="thumbs_up") and not st.session_state['feedback_given']:
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Positive", st.session_state['program_ran'], st.session_state['pl_id_NL_SQL'])
        st.success("Thanks for the feedback! 👍")
        st.session_state['feedback_given'] = True
        
    if thumbs_down.button("👎", key="thumbs_down") and not st.session_state['feedback_given']:
        save_feedback(natural_language_input, st.session_state['SQL_query'], "Negative", st.session_state['program_ran'], st.session_state['pl_id_NL_SQL'])
        st.error("Thanks for the feedback, we're working on it!")
        st.session_state['feedback_given'] = True
        

# Close the connection to the database
conn.close()