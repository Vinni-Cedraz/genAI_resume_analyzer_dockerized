#!/usr/bin/zsh

# Check if GROQ_API_KEY is empty
if [ -z "$GROQ_API_KEY" ]; then
  echo "Error: GROQ_API_KEY is not set or is empty."
  exit 1
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

echo "GROQ_API_KEY=$GROQ_API_KEY" > .env
echo "MODEL=$MODEL" >> .env

docker-compose up --build

# Wait for the API to be ready
echo "Waiting for Flask API to be ready..."
while ! curl -s http://localhost:5000/health; do
  echo "API not ready yet..."
  sleep 5
done
echo "Flask API is ready!"

# Run the Streamlit app
echo "All containers are up and running!"
echo -e '\e]8;;http://localhost:8501/\e\\Click here\e]8;;\e\\'
