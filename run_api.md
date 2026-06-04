python -m venv .venv

.\.venv\Scripts\activate

pip install pymupdf --prefer-binary

pip install flask==3.0.3 flask-cors==4.0.0 cryptography==42.0.8 pymongo==4.7.3 mongomock==4.1.2 python-dotenv==1.0.1 gunicorn==22.0.0

copy .env.example .env

python anonimizador.py

python banco_dados.py

python seguranca.py

python mongo_service.py

(caso de erro) python fix_mongo.py

python mongo_service.py

python api_backend.py