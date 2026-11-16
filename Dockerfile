FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn
COPY rta rta
COPY config config
RUN useradd --create-home app
USER app
EXPOSE 8000
# Set RTA_MODEL_URL, RTA_MODEL_KEY and RTA_MODEL_NAME to use a model; without them unknown subjects go to an engineer.
CMD ["uvicorn", "rta.product.service:app", "--host", "0.0.0.0", "--port", "8000"]
