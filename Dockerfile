FROM python:3.9-buster

ENV PYTHONUNBUFFERED=1

WORKDIR /ars
COPY . /ars/ 

RUN apt-get update && apt install -y netcat
#New Relic Install
RUN pip install --no-cache-dir newrelic

RUN mv newrelic.ini /ars/.pyenv-python3.9/lib/python3.9/site-packages/newrelic/

COPY requirements.txt /ars/
RUN pip install -r requirements.txt

RUN mv wait-for /bin/wait-for

# Set the entrypoint for New Relic monitoring
ENTRYPOINT ["newrelic-admin", "run-program"]
