FROM python:3.10.8-slim-buster


# set working directory
WORKDIR /usr/src/app

RUN mkdir /usr/src/app/logs
RUN chmod 777 /usr/src/app/logs 

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
  && apt-get -y install gcc postgresql \
  && apt-get install -y netcat \
  && apt-get install -y build-essential \
  && apt-get install -y libpq-dev \
  && apt-get install -y git \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && apt-get clean  

RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install --default-timeout=1000 -r requirements.txt

COPY ./entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

COPY ./satnam/start.sh /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

COPY ./celery/worker/start.sh /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./celery/beat/start.sh /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./celery/flower/start.sh /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower



COPY . .

ENTRYPOINT [ "/usr/src/app/entrypoint.sh" ]