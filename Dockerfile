FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG PIP_NO_CACHE_DIR=1

# Install Chromium. chromium-driver provides a native chromedriver at
# /usr/bin/chromedriver, which is required on ARM: undetected_chromedriver only
# downloads x86-64 driver builds, so on ARM the bundled driver is used instead
# (see flathunter/chrome_wrapper.py:get_system_chromedriver_path).
RUN apt-get -y update
RUN apt-get install -y chromium chromium-driver

# Upgrade pip, install pipenv
RUN pip install --upgrade pip
RUN pip install pipenv

WORKDIR /usr/src/app

# Copy files that list dependencies
COPY Pipfile.lock Pipfile ./

# Generate requirements.txt and install dependencies from there
RUN pipenv requirements > requirements.txt
RUN pip install -r requirements.txt

# Copy all other files, including source files
COPY . .
