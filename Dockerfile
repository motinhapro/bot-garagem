FROM python:3.9-slim

# Define onde as coisas vão ficar dentro do container
WORKDIR /app

# Instala dependências básicas do Linux
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 1. Copia só o requirements primeiro (para aproveitar cache do Docker)
COPY requirements.txt .

# 2. Instala as bibliotecas dentro do container
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copia todo o resto
COPY . .

# Expõe as portas
EXPOSE 8000
EXPOSE 8501

# Roda a API em segundo plano e o Dashboard na frente
CMD sh -c "uvicorn main:app --app-dir Python --host 0.0.0.0 --port 8000 & streamlit run Python/dashboard.py --server.port 8501 --server.address 0.0.0.0"