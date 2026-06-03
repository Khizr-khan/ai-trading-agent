from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print('URL:', url)
print('KEY:', key[:20], '...')

sb = create_client(url, key)
res = sb.table('portfolio').select('*').execute()
print('Result:', res.data)