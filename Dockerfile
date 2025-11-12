# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS setup

# ---------------------------------------------------------------------
# 1) Add deadsnakes PPA so python3.11 exists
RUN apt-get update -y \
 && apt-get install -y --no-install-recommends software-properties-common \
 && add-apt-repository -y ppa:deadsnakes/ppa \
 && apt-get update -y

# ---------------------------------------------------------------------
# TODO: Remove most of these packages later
# 2) Install all packages (pip fix: add python3-pip, then symlink pip → pip3)
RUN apt-get install -y --no-install-recommends \
  htop \
  vim \
  openssl \
  ca-certificates \
  curl \
  wget \
  sudo \
  bash \
  net-tools \
  novnc \
  x11vnc \
  xvfb \
  xfce4 \
  python3.11 \
  python3.11-dev \
  python3.11-venv \
  python3.11-tk \
  python3.11-distutils \
  python3-pip \
  locales \
  libpq5 \
  sqlite3 \
  dbus-x11 \
  xfce4-terminal \
  xfonts-base \
  xdotool \
  psmisc \
  scrot \
  imagemagick \
  pm-utils \
  build-essential \
  python-is-python3 \
  unzip \
  git \
  xauth \
  ffmpeg \
  nginx \
  apache2 \
  libapache2-mod-wsgi-py3 \
  gnupg \
  gpg \
  jq \
  python3 \
  make \
  gcc \
  g++ \
  libcairo2-dev \
  libjpeg-turbo8-dev \
  libpng-dev \
  libwebp-dev \
  libtiff-dev \
  libgif-dev \
  libvips-dev \
  libgstreamer1.0-0 \
  libgtk-4-1 \
  libgraphene-1.0-0 \
  libwoff1 \
  libevent-2.1-7t64 \
  libgstreamer-plugins-base1.0-0 \
  libgstreamer-plugins-good1.0-0 \
  libgstreamer-gl1.0-0 \
  libgstreamer-plugins-bad1.0-0 \
  libavif16 \
  libenchant-2-2 \
  libsecret-1-0 \
  libhyphen0 \
  libmanette-0.2-0 \
  libgles2

# TODO: remove this after testing
RUN echo "ubuntu ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# make a `pip` alias for scripts that expect it
RUN ln -sf /usr/bin/pip3 /usr/bin/pip

# keep node-gyp on Python 3.11
ENV npm_config_python=/usr/bin/python3.11

RUN update-ca-certificates

# ---------------------------------------------------------------------
# Install Chromium browser from Debian repos (has ARM64 support)
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O /etc/apt/keyrings/debian-archive-key.asc https://ftp-master.debian.org/keys/archive-key-12.asc && \
    echo 'deb [signed-by=/etc/apt/keyrings/debian-archive-key.asc] http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list.d/debian.list && \
    apt-get update && \
    apt-get install -y chromium chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# disable sandboxing for chromium (won't run in docker)
RUN echo "export CHROMIUM_FLAGS=--no-sandbox" >> /etc/chromium.d/default-flags
RUN mkdir -p /etc/chromium/policies/managed
RUN echo '{ "DnsOverHttpsMode": "off", "DefaultPopupsSetting": 1, "SafeBrowsingProtectionLevel": 1 }' > /etc/chromium/policies/managed/policy.json


# Install Chromium browser from Debian repos (has ARM64 support)
RUN mkdir -p /etc/apt/keyrings && \
    wget -q -O /etc/apt/keyrings/debian-archive-key.asc https://ftp-master.debian.org/keys/archive-key-12.asc && \
    echo 'deb [signed-by=/etc/apt/keyrings/debian-archive-key.asc] http://deb.debian.org/debian bookworm main' > /etc/apt/sources.list.d/debian.list && \
    apt-get update && \
    apt-get install -y chromium chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# disable sandboxing for chromium (won't run in docker)
RUN echo "export CHROMIUM_FLAGS=--no-sandbox" >> /etc/chromium.d/default-flags
# disable dns over https (so we can mock websites)
RUN mkdir -p /etc/chromium/policies/managed
# note that this is edited during startup to append insecure sites as secure
RUN echo '{ "DnsOverHttpsMode": "off", "DefaultPopupsSetting": 1, "SafeBrowsingProtectionLevel": 1 }' > /etc/chromium/policies/managed/policy.json

WORKDIR /
RUN chmod 777 /usr/local/bin

# Setup and start dinit
COPY dinit.d/ /etc/dinit.d/
RUN mkdir -p /var/log/dinit && chmod 755 /var/log/dinit

# Install nvm for ubuntu user
USER ubuntu
ENV HOME=/home/ubuntu \
    NVM_DIR=/home/ubuntu/.nvm

# Install latest nvm (v0.39.7) <TEMPLATE> language
# RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# ------------------------- <TEMPLATE> setup -------------------------

# configure git
RUN git config --global user.email "agent@example.com" && \
    git config --global user.name "mr agent"

# Clone ClickHouse repository
ENV REPO_VERSION=1.0
WORKDIR /home/ubuntu
RUN git clone https://github.com/ClickHouse/ClickHouse.git;

WORKDIR /home/ubuntu/ClickHouse

USER ubuntu
WORKDIR /

# Set environment variables
ENV HOME=/home/ubuntu \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1.0 \
    DISPLAY_WIDTH=1400 \
    DISPLAY_HEIGHT=850

EXPOSE 6080

# supress AT-SPI errors
ENV NO_AT_BRIDGE=1

# ================================================ MCP SERVER SETUP ================================================
FROM setup AS runtime

USER root

ENV WIDTH=1400 \
    HEIGHT=850 \
    DISPLAY_NUM=1 \
    SCREENSHOT_DIR=/home/ubuntu/screenshots \
    DOWNLOADS_DIR=/home/ubuntu/Downloads \
    RUST_LOG=warn
RUN mkdir -p /home/ubuntu/screenshots && chmod 777 /home/ubuntu/screenshots && \
    mkdir -p /home/ubuntu/Downloads && chmod 777 /home/ubuntu/Downloads && \
    chmod 777 /home/ubuntu/Downloads && \
    chmod 777 /root

# prepare for the mcp server
RUN pip install uv --break-system-packages

# copy python files
COPY ./src /mcp_server/src
COPY ./pyproject.toml /mcp_server/pyproject.toml
COPY ./README.md /mcp_server/README.md

RUN cd /mcp_server && uv venv && . .venv/bin/activate && uv sync && uv pip install -e .
ENV PYTHONPATH=/mcp_server/.venv/lib/python3.10/site-packages
ENV PATH=/mcp_server/.venv/bin:$PATH

EXPOSE 6080 3000

ARG PROBLEM_ID=<TEMPLATE>
ENV PROBLEM_ID=$PROBLEM_ID

ARG HINTS="none"
ENV HINTS=$HINTS

CMD ["hud_eval"]
