# Streamlit user interface
import streamlit as st
import sqlite3
import pandas as pd
import os
from pathlib import Path
import openai
import promptlayer
from dotenv import load_dotenv
import random

# Load environment variables from .env file
load_dotenv()
promptlayer.api_key = os.environ.get('PROMPTLAYER_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY
promptlayer.openai.api_key = OPENAI_API_KEY

# Function to refine SQL query using PromptLayer
def refine_sql_with_promptlayer(natural_language, columns, pl_group_id):
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
        return_pl_id=True,
        pl_tags=["Generate-SQL"]
    )
    
    # Associate request to Prompt Template
    promptlayer.track.prompt(request_id=pl_id, 
        prompt_name='NL_to_SQL', prompt_input_variables=variables)
    
    promptlayer.track.group(
        request_id=pl_id, 
        group_id=pl_group_id
    )

    refined_sql = response.choices[0].message.content
    return refined_sql, pl_id

#convert the SQL response to a natural language answer
def sql_to_NL_answer(df, natural_language, pl_group_id):
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
        return_pl_id=True,
        pl_tags=["Explain-SQL"]
    )
    
    # Associate request to Prompt Template
    promptlayer.track.prompt(request_id=pl_id, 
        prompt_name='SQL to NL', prompt_input_variables=variables)
    
    #group prompts
    promptlayer.track.group(
        request_id=pl_id, 
        group_id=pl_group_id
    )
    
    #add metadata
    promptlayer.track.metadata(
        request_id=pl_id,
        metadata={
            "User_ID":st.session_state['User_ID']
        }
    )

    NL_answer = response.choices[0].message.content
    return NL_answer, pl_id

#function to handle feedback
def handle_positive_feedback():
    # Update session state to indicate feedback has been given
    st.session_state['feedback_given'] = True
    st.session_state['temp'] = True  # It seems you're using 'temp' as an additional flag; ensure its role is clear and necessary
    
    # Perform your feedback logic here
    promptlayer.track.metadata(
        request_id=st.session_state['pl_id_NL_SQL'],
        metadata={
            "Feedback": "Positive",
            "User_ID":st.session_state['User_ID']
        }
    )
    promptlayer.track.metadata(
        request_id=st.session_state['pl_id_SQL_NL'],
        metadata={
            "Feedback": "Positive",
            "User_ID":st.session_state['User_ID']
        }
    )
    # Display success message
    st.success("Thanks for the feedback! 👍")

#function to handle feedback
def handle_negative_feedback():
    # Similar update for negative feedback
    st.session_state['feedback_given'] = True
    st.session_state['temp'] = True
    
    # Negative feedback logic
    promptlayer.track.metadata(
        request_id=st.session_state['pl_id_NL_SQL'],
        metadata={
            "Feedback": "Negative",
            "User_ID":st.session_state['User_ID']
        }
    )
    promptlayer.track.metadata(
        request_id=st.session_state['pl_id_SQL_NL'],
        metadata={
            "Feedback": "Negative",
            "User_ID":st.session_state['User_ID']
        }
    )
    # Display error message
    st.error("Thanks for the feedback, we're working on it!")
    
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
if 'User_ID' not in st.session_state:
    st.session_state['User_ID'] = "Streamlit_"+str(random.randint(10000000, 99999999))
if 'Group_ID' not in st.session_state:
    st.session_state['Group_ID'] = promptlayer.group.create()
if 'Result_Generated' not in st.session_state:
    st.session_state['Result_Generated'] = False
if 'starter_question' not in st.session_state:
    starter_questions = ["How many different ship names are there?", "What is the difference in the average freight cost between Lyon and Rio de Janeiro?", "What is the employee ID that handled the most orders?", "Which country received the highest number of orders?", "List all orders placed by customer LEHMS"]
    st.session_state['starter_question'] = starter_questions[random.randint(0,5)]
if 'temp' not in st.session_state:
    st.session_state['temp'] = False

#Choose a random starter question
natural_language_input = st.text_input("Enter your question:", st.session_state['starter_question'])

if st.button("Generate Response", key="submit"):
    st.session_state['Group_ID'] = promptlayer.group.create()
    st.session_state['SQL_query'], pl_id_NL_SQL = refine_sql_with_promptlayer(natural_language_input, column_data_string, st.session_state['Group_ID'])
    st.session_state['pl_id_NL_SQL'] = pl_id_NL_SQL
    st.session_state['feedback_given'] = False
    st.session_state['program_ran'] = False
    st.session_state['Result_Generated'] = False
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        st.session_state['program_ran'] = True
        #score 100 if the SQL runs
        promptlayer.track.score(
            request_id=pl_id_NL_SQL,
            score=100
        )
        #add metadata
        promptlayer.track.metadata(
            request_id=st.session_state['pl_id_NL_SQL'],
            metadata={
                "User_ID":st.session_state['User_ID']
            }
        )  
    except Exception as e:
        st.session_state['program_ran'] = False
        #score 0 if the SQL did not run
        promptlayer.track.score(
            request_id=pl_id_NL_SQL,
            score=0
        )
        #add the metadata
        promptlayer.track.metadata(
            request_id=st.session_state['pl_id_NL_SQL'],
            metadata={
                "User_ID":st.session_state['User_ID']
            }
        )  
        st.error(f"Error executing query: {e}")
        
# Ensure the SQL result remains displayed after feedback
if st.session_state['program_ran'] and not st.session_state['Result_Generated']:
    # st.write("SQL Query: %s" % (st.session_state['SQL_query'])) #uncomment this to write out the SQL Query
    try:
        df = pd.read_sql_query(st.session_state['SQL_query'], conn)
        NL_answer, st.session_state['pl_id_SQL_NL']  = sql_to_NL_answer(df, natural_language_input, st.session_state['Group_ID'])
        st.session_state['Result_Generated'] = True #issued
        #add the metadata
        promptlayer.track.metadata(
            request_id=st.session_state['pl_id_NL_SQL'],
            metadata={
                "User_ID":st.session_state['User_ID']
            }
        )  
        st.write(df) #write section of database used to answer question
        st.write(NL_answer) #write the question in natural language
    except Exception as e:
        st.error(f"Error displaying query result: {e}")
        st.session_state['program_ran'] = False
   
# Conditional rendering of feedback buttons
if st.session_state['program_ran'] and not st.session_state['feedback_given']:
    st.write("Rate your result:")
    thumbs_up, thumbs_down = st.columns(2)
    thumbs_up.button("👍", key="thumbs_up", on_click=handle_positive_feedback)
    thumbs_down.button("👎", key="thumbs_down", on_click=handle_negative_feedback)

# Close the connection to the database
conn.close()