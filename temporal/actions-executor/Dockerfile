FROM python:3.10

ENV VIRTUAL_ENV=/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies:
COPY ./temporal/actions-executor/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY ./temporal/actions-executor/ .
# Run the application:
CMD ["python3","main.py"]
