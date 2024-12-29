cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebserver
poetry run uvicorn webserver.main:app --reload


docker run --name assistantdb -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres
docker run -d --name chatdb -p 27017:27017 -e MONGO_INITDB_DATABASE=my_database mongo
docker run --name my-memcache -d memcached

# TODO: keep EBS for big files like images
# TODO: FIX error Directory C:\Users\alexa\Desktop\Development\SecondBrain\Assistant\assistant for assistant does not seem to be a Python package