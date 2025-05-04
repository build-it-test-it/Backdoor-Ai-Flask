---
name: Docker
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - docker
  - container
  - image
  - dockerfile
  - docker-compose
  - containerization
---

# Docker Microagent

This microagent provides knowledge and capabilities for working with Docker containers and images.

## Basic Docker Commands

### Container Management

```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# Start a container
docker start container_name_or_id

# Stop a container
docker stop container_name_or_id

# Remove a container
docker rm container_name_or_id

# Run a container
docker run [options] image_name [command]

# Execute a command in a running container
docker exec -it container_name_or_id command
```

### Image Management

```bash
# List images
docker images

# Pull an image
docker pull image_name:tag

# Build an image from a Dockerfile
docker build -t image_name:tag .

# Remove an image
docker rmi image_name:tag

# Tag an image
docker tag source_image:tag target_image:tag

# Push an image to a registry
docker push image_name:tag
```

### Volume Management

```bash
# List volumes
docker volume ls

# Create a volume
docker volume create volume_name

# Remove a volume
docker volume rm volume_name

# Inspect a volume
docker volume inspect volume_name
```

### Network Management

```bash
# List networks
docker network ls

# Create a network
docker network create network_name

# Remove a network
docker network rm network_name

# Connect a container to a network
docker network connect network_name container_name

# Disconnect a container from a network
docker network disconnect network_name container_name
```

## Dockerfile Basics

A Dockerfile is a text document that contains all the commands a user could call on the command line to assemble an image.

Example Dockerfile:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

## Docker Compose

Docker Compose is a tool for defining and running multi-container Docker applications.

Example docker-compose.yml:

```yaml
version: '3'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - .:/app
    environment:
      - FLASK_ENV=development
    depends_on:
      - db
  db:
    image: postgres:13
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_USER=user
      - POSTGRES_DB=mydb

volumes:
  postgres_data:
```

## Best Practices

1. Use specific image tags instead of `latest`
2. Minimize the number of layers in your Dockerfile
3. Use multi-stage builds for smaller images
4. Don't run containers as root
5. Use volume mounts for persistent data
6. Use environment variables for configuration
7. Clean up unused containers, images, and volumes regularly

## Troubleshooting

Common Docker issues:

- Container won't start: Check logs with `docker logs container_name`
- Permission denied: May need to run with `sudo` or add user to docker group
- Port already in use: Change the host port mapping
- Out of disk space: Run `docker system prune` to clean up unused resources
- Network connectivity issues: Check network settings and firewall rules