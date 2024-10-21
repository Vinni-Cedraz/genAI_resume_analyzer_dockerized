#!/usr/bin/zsh

# Check if GROQ_API_KEY is empty
if [ -z "$GROQ_API_KEY" ]; then
  echo "Error: GROQ_API_KEY is not set or is empty."
  exit 1
fi

# Stop and remove existing containers if they are running
if sudo docker ps -a --format '{{.Names}}' | grep -q flask_container; then
  echo "stopping and removing previous flask_container..."
  sudo docker stop flask_container
  sudo docker rm flask_container
fi
if sudo docker ps -a --format '{{.Names}}' | grep -q streamlit_container; then
  echo "stopping and removing previous streamlit_container..."
  sudo docker stop streamlit_container
  sudo docker rm streamlit_container
fi

# Ask the user for the LLM size
echo "Do you want an LLM of what size? (8b or 70b)"
read LLM_SIZE

if [ "$LLM_SIZE" = "8b" ]; then
  echo "Have you already exceeded the limit of requests per day? (yes or no)"
  read EXCEEDED_LIMIT
  if [ "$EXCEEDED_LIMIT" = "no" ]; then
    MODEL="llama-3.1-8b-instant"
  elif [ "$EXCEEDED_LIMIT" = "yes" ]; then
    MODEL="llama3-8b-8192"
  else
    echo "Invalid answer. Run the script again and answer only 'yes' or 'no'."
    exit 1
  fi
elif [ "$LLM_SIZE" = "70b" ]; then
  echo "Have you already exceeded the limit of requests per day? (yes or no)"
  read EXCEEDED_LIMIT
  if [ "$EXCEEDED_LIMIT" = "no" ]; then
    MODEL="llama-3.1-70b-versatile"
  elif [ "$EXCEEDED_LIMIT" = "yes" ]; then
    MODEL="llama3-70b-8192"
  else
    echo "Invalid answer. Run the script again and answer only 'yes' or 'no'."
    exit 1
  fi
else
  echo "Invalid LLM size. Please enter either '8b' or '70b'."
  exit 1
fi

# create a docker network
sudo docker network create myapp_network

# Build the images
sudo docker build -t base_image -f Dockerfile.base .
sudo docker build -t flask_api -f Dockerfile.flask .
sudo docker build -t streamlit_app -f Dockerfile.streamlit .

# Run the Flask API container
sudo docker run -d --name flask_container --network myapp_network -p 5000:5000 -e HUGGINGFACEHUB_API_TOKEN="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" flask_api

# Wait for the API to be ready
echo "Waiting for Flask API to be ready..."
while ! curl -s http://localhost:5000/health; do
  echo "API not ready yet..."
  sleep 5
done
echo "Flask API is ready!"

# Run the Streamlit app
sudo docker run -d --name streamlit_container --network myapp_network -p 8501:8501 -e GROQ_API_KEY=${GROQ_API_KEY} -e MODEL=${MODEL} streamlit_app

echo "All containers are up and running!"
echo -e '\e]8;;http://localhost:8501/\e\\Click here\e]8;;\e\\'
