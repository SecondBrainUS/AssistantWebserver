Goal:
    Multiple users, multiple sessions connected to a single AI agent
    Realtime/Websocket or RESTful/HTTP 

    AI APIs:
        OpenAI Realtime
        Ollama (next)


    The Room needs to be able to emit a message to all connected users

    Room:
      room_id
      socket
      chat_id?
      connected_users
      connection_manager

      # connection stuff:
        _ai_api_connection_attempts
        MAX_CONNECTION_ATTEMPTS

      _broadcast()
          {
            room_id
          }
          sio.emit('room_joined', 
                        {data}, 
                        room=sid, 
                        namespace=self.namespace
                    )

      _on_first_message()
        create chat_id





On send_message, in the assistant namespace we override the message callback so it responds to the room when OpenAI responds.



cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebserver
poetry run uvicorn webserver.main:app --reload

poetry update assistant
poetry install

cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebDeployment\local
docker-compose up -d --force-recreate --build assistant_webserver


cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebClient\assistant-web-client
npm run dev

docker-compose build --no-cache assistant_webclient
docker-compose up -d --force-recreate assistant_webclient

poetry update assistant
poetry install
docker build --no-cache -t assistant_webserver .
OR
docker-compose build assistant_webserver
docker-compose up -d assistant_webserver

docker run --name assistantdb -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres
docker run -d --name chatdb -p 27017:27017 -e MONGO_INITDB_DATABASE=my_database mongo
docker run --name my-memcache -p 11211:11211 -d memcached
docker build -t sb-web-nginx .
docker run -d --name sb-web-nginx -p 8090:80 sb-web-nginx

docker run --name assistant_webserver -d -p 8000:8000 assistant_webserver

# TODO: keep EBS for big files like images
# TODO: FIX error Directory C:\Users\alexa\Desktop\Development\SecondBrain\Assistant\assistant for assistant does not seem to be a Python package

NGNIX CONFIG:
events {}

http {
    map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
    }
    
    upstream api_upstream {
        server host.docker.internal:8000;
    }

    upstream frontend_upstream {
        server host.docker.internal:3000;
    }

    server {
        listen 80;
        
        # Add these headers for cookie handling
        proxy_cookie_path / "/";
        proxy_cookie_domain localhost $host;

        location /socket.io/ {
            proxy_pass http://api_upstream;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_set_header Cookie $http_cookie;
            
            # Cookie handling
            proxy_cookie_path / "/";
            proxy_cookie_domain localhost $host;
        }

        location / {
            proxy_pass http://frontend_upstream;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Cookie $http_cookie;
            
            # Cookie handling
            proxy_cookie_path / "/";
            proxy_cookie_domain localhost $host;
        }

        location /api {
            proxy_pass http://api_upstream;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_set_header Cookie $http_cookie;
            
            # Cookie handling
            proxy_cookie_path / "/";
            proxy_cookie_domain localhost $host;
        }

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options SAMEORIGIN;
        add_header X-XSS-Protection "1; mode=block";
    }
}

prompt for observability and monitoring

I have a few python applications that i develop locally and deploy for production on AWS Fargate. I run these apps in docker for both local dev and production.

I'd like to add observabilility and monitoring with prometheus, loki, and grafana. These should work for both local and production. id like to use promtail to feed the logs into loki. For production, id like to have long term storage in S3 using mimir.

write a docker compose for the local environment
write a cloud formation config for the production environment

write configs for loki, prometheus, promtail, and grafana for both local and production.

think carefully about the configurations. follow best practices.

write example python code for prometheus counters.

Prometheus mini example code
from prometheus_client import Counter
REQUESTS = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
ERRORS = Counter('http_errors_total', 'Total HTTP errors', ['method', 'endpoint'])

for local, 1 promtail for all apps
for prod, 1 promtail per app

for local, for multi app:
scrape_configs:
  - job_name: app1
    static_configs:
      - targets: ['localhost']
        labels:
          job: app1
          environment: local
          __path__: C:/path/to/app1/logs/*.log

  - job_name: app2
    static_configs:
      - targets: ['localhost']
        labels:
          job: app2
          environment: local
          __path__: C:/path/to/app2/logs/*.log
