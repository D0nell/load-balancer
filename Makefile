.PHONY: all build up down clean logs

all: build up

build:
	docker build -t server-image:latest ./server
	docker build -t load-balancer-image:latest ./load_balancer

up:
	docker compose up -d

down:
	docker compose down
	docker ps -a -q --filter "ancestor=server-image:latest" | xargs -r docker stop | xargs -r docker rm

clean: down
	docker rmi -f server-image:latest load-balancer-image:latest

logs:
	docker logs -f load_balancer_cb