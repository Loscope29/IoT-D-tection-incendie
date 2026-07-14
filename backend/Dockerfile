FROM python:3.10-slim

WORKDIR /app

# Empecher Python d'écrire des fichiers .pyc sur le disque
ENV PYTHONDONTWRITEBYTECODE 1
# Empecher Python de mettre en mémoire tampon stdout et stderr
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exposer le port par défaut de Django
EXPOSE 8002

# Commande de démarrage par défaut (sera surchargée ou lancera runserver après migration)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8002"]
