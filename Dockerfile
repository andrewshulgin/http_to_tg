FROM python:3-alpine
LABEL opencontainers.image.authors="Andrew Shulgin <andrewshulginua@gmail.com>"

RUN ["apk", "add", "build-base"]
COPY ./requirements.txt /home/http_to_tg/requirements.txt
WORKDIR /home/http_to_tg
RUN ["pip3", "install", "-r", "requirements.txt"]
RUN ["mkdir", "-p", "/mnt/data"]
RUN ["chown", "nobody", "/mnt/data"]
COPY . /home/http_to_tg
USER nobody
EXPOSE 3001
VOLUME ["/mnt/data"]

CMD ["./main.py"]
