FROM python:3.10
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app
COPY run.py /app/
EXPOSE 8000
CMD ["python", "run.py"]