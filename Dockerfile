# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements.txt file into the container at /usr/src/app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN python -m venv venv310
RUN . venv310/bin/activate && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run app.py when the container launches
CMD [ "venv310/bin/python", "scraper.py" ]