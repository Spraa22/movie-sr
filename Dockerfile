# Stable Python 3.11 version use kar rahe hain taaki Pyrogram crash na ho
FROM python:3.11-slim

# System updates aur zaroori build tools install karein
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Working directory set karein
WORKDIR /app

# Sabse pehle requirements copy karke dependencies install karein (Fast build cache ke liye)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Baki saara project code copy karein
COPY . .

# Bot run karne ki command (agar aapki file ka naam bot.py hai toh yahan bot.py rakhein)
CMD ["python", "main.py"]
