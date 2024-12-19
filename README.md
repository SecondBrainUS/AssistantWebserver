cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebserver
poetry run uvicorn webserver.main:app --reload

# TODO: keep EBS for big files like images

docker run --name assistantdb -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres