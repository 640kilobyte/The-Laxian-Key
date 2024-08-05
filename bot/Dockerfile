# контейнер бота

FROM python:3.11-bookworm
# WORKDIR был проигнорироваен умышленно -
# даже в контйнере кидать все в корень
# мне не позволяет советсть
COPY app /app
RUN pip install -r /app/requirements.txt
CMD python3 /app/main.py