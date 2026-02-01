from dotenv import load_dotenv
import os
load_dotenv()

user=os.getenv('user')
host=os.getenv('host')
port=os.getenv('port')
password=os.getenv('password')
dbname=os.getenv('dbname')
tg_key=os.getenv('tg_key')
deepseek_key=os.getenv('deepseek_key')
qdrant_url=os.getenv('qdrant_url')
qdrant_key=os.getenv('qdrant_key')