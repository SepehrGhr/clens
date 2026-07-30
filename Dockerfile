FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY README.md ./

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /bin/false clens
USER clens

ENTRYPOINT ["clens"]
CMD ["--help"]
