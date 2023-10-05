FROM python:3.10

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies:
COPY ./temporal/worker/ .
RUN pip install -r requirements.txt
# Run the application:
CMD ["python3","main.py"]
