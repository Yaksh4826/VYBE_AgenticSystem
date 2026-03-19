import os
from supabase import Client, create_client
from dotenv import load_dotenv

load_dotenv()

url : str = os.environ['SUPABASE_PROJECT_URL']
key :str = os.environ['SUPABASE_KEY']

supabase : Client = create_client(url, key)