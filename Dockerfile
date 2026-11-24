FROM python:3.11-slim
RUN useradd -m -u 1000 user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH U2NET_HOME=/home/user/.u2net
WORKDIR /home/user/app
USER user
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p $U2NET_HOME && python -c "import urllib.request as u;u.urlretrieve('https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx','/home/user/.u2net/u2netp.onnx')"
COPY --chown=user app.py .
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860"]
