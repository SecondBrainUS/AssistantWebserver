cd C:\Users\alexa\Desktop\Development\SecondBrain\AssistantWebserver
poetry run uvicorn webserver.main:app --reload


docker run --name assistantdb -e POSTGRES_PASSWORD=password -d -p 5432:5432 postgres
docker run -d --name chatdb -p 27017:27017 -e MONGO_INITDB_DATABASE=my_database mongo
docker run --name my-memcache -d memcached

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