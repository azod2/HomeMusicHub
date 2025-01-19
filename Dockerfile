FROM python:3.11-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

RUN apt-get update && apt-get install -y ffmpeg

COPY . .

EXPOSE 5000

CMD ["python3", "app.py"]
