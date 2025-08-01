# Usa un'immagine Python ufficiale come base
FROM python:3.9-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Copia i file dei requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installa spotdl
RUN pip install --no-cache-dir spotdl

# Copia il resto dell'applicazione nel container
COPY . .

# Esponi la porta su cui girerà Flask
EXPOSE 5001

# Comando per avviare l'applicazione
CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
