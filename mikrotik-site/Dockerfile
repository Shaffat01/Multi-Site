FROM python:3.9-slim

# ১. কন্টেইনারের ভেতর ওয়ার্কিং ডিরেক্টরি সেট করা
WORKDIR /app

# ২. requirements.txt কপি এবং ডিপেন্ডেন্সি ইনস্টল
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ৩. ডাটাবেস এবং মাইক্রোটিক লাইব্রেরিগুলো ইনস্টল (নিশ্চিত হওয়ার জন্য আলাদাভাবে দেওয়া হলো)
RUN pip install gunicorn psycopg2-binary librouteros paramiko

# ৪. প্রজেক্টের সব কোড কপি করা
COPY . .

# ৫. পোর্ট ৯০০০ এক্সপোজ করা (Nginx এর সাথে কথা বলার জন্য)
EXPOSE 9000

# ৬. Gunicorn দিয়ে প্রোডাকশন সার্ভারে অ্যাপ রান করা
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:9000", "app:app"]