# Use official Python image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose port
EXPOSE 5090

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5090"]