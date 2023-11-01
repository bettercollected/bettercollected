FROM selenium/standalone-chrome:118.0

RUN sudo apt-get update

RUN sudo apt install  python3.8-venv -y

ENV VIRTUAL_ENV=/home/seluser/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /home/seluser/
# Install dependencies:
COPY ./temporal/worker/ .
RUN pip install -r requirements.txt
# Run the application:
CMD ["python3","main.py"]
