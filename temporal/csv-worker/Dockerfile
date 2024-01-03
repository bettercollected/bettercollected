FROM joyzoursky/python-chromedriver

ENV VIRTUAL_ENV=/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies:
COPY ./temporal/worker/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY ./temporal/csv-worker/ .
# Run the application:
CMD ["python3","main.py"]
