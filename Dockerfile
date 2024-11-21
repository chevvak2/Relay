FROM python:3.9-buster

ENV PYTHONUNBUFFERED=1

WORKDIR /ars

RUN apt-get update && apt install -y netcat
#New Relic Install
RUN pip install --no-cache-dir newrelic


COPY requirements.txt /ars/
RUN pip install -r requirements.txt
COPY . /ars/ 
RUN mv wait-for /bin/wait-for

# Set the entrypoint for New Relic monitoring
ENTRYPOINT ["newrelic-admin", "run-program"]
