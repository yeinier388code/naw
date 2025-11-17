#!/bin/bash
pip3.13 install --user -r /home/yeinier/bot_telegram/requirements.txt
echo "Dependencias instaladas"

# Instalar ffmpeg si no existe
if [ ! -f ~/bin/ffmpeg ]; then
    mkdir -p ~/bin && cd ~/bin
    wget -O ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
    tar xvf ffmpeg.tar.xz
    mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe .
    chmod a+rx ffmpeg ffprobe
    echo "ffmpeg instalado"
else
    echo "ffmpeg ya estaba instalado"
fi
