# Use an official Python runtime as a parent image
FROM python:3.11-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variables (can be overridden at runtime)
# These are placeholders. You'll pass actual secrets via docker run -e or docker-compose
ENV LINKEDIN_CLIENT_ID=""
ENV LINKEDIN_CLIENT_SECRET=""
ENV LINKEDIN_REDIRECT_URI="http://localhost:8000/callback"
ENV GEMINI_API_KEY=""

# Run app.py using uvicorn when the container launches
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]