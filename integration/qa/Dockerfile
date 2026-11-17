FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /qa
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY integration/qa/test_flow.py integration/qa/test_flow.py
CMD ["python", "-m", "pytest", "-q", "integration/qa/test_flow.py"]
