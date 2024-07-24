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
  && apt-get clean  

RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install --default-timeout=1000 -r requirements.txt

COPY ./entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh




COPY . .

ENTRYPOINT [ "/usr/src/app/entrypoint.sh" ]