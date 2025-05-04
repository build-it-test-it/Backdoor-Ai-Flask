"""
Docker runtime implementation for Backdoor.
Adapted from OpenHands with modifications for Backdoor Flask app.
"""
import os
import time
import uuid
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Union

import docker
import httpx
import tenacity
from docker.models.containers import Container

from app.backdoor.core.config import AppConfig
from app.backdoor.core.exceptions import (
    AgentRuntimeDisconnectedError,
    AgentRuntimeNotFoundError,
    DockerConnectionError,
    DockerNotFoundError,
    DockerTimeoutError,
)
from app.backdoor.core.logger import get_logger

logger = get_logger("runtime.docker")

CONTAINER_NAME_PREFIX = 'backdoor-runtime-'

EXECUTION_SERVER_PORT_RANGE = (30000, 39999)
VSCODE_PORT_RANGE = (40000, 49999)
APP_PORT_RANGE_1 = (50000, 54999)
APP_PORT_RANGE_2 = (55000, 59999)


def _is_retryable_error(exception):
    """Check if an exception is retryable."""
    if isinstance(exception, tenacity.RetryError):
        cause = exception.last_attempt.exception()
        return _is_retryable_error(cause)

    return isinstance(
        exception,
        (
            ConnectionError,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ),
    )


def find_available_tcp_port(start_port: int, end_port: int) -> int:
    """Find an available TCP port in the given range."""
    import socket
    
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    
    raise RuntimeError(f"No available TCP port found in range {start_port}-{end_port}")


def stop_all_containers(prefix: str = CONTAINER_NAME_PREFIX):
    """Stop all containers with the given prefix."""
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": prefix})
        
        for container in containers:
            try:
                container.stop(timeout=5)
                logger.info(f"Stopped container: {container.name}")
            except Exception as e:
                logger.error(f"Error stopping container {container.name}: {e}")
                
    except Exception as e:
        logger.error(f"Error stopping containers: {e}")


class DockerRuntime:
    """Docker runtime for Backdoor agents.
    
    This runtime manages Docker containers for agent execution.
    """
    
    _shutdown_listener_id: Optional[uuid.UUID] = None
    
    def __init__(
        self,
        config: AppConfig,
        sid: str = 'default',
        plugins: Optional[List[Dict[str, Any]]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        status_callback: Optional[Callable] = None,
        attach_to_existing: bool = False,
        headless_mode: bool = True,
    ):
        """Initialize the Docker runtime.
        
        Args:
            config: The application configuration.
            sid: The session ID.
            plugins: List of plugin requirements.
            env_vars: Environment variables to set.
            status_callback: Callback function for status updates.
            attach_to_existing: Whether to attach to an existing container.
            headless_mode: Whether to run in headless mode.
        """
        # Register shutdown handler if not already registered
        if not DockerRuntime._shutdown_listener_id:
            DockerRuntime._shutdown_listener_id = uuid.uuid4()
            # Register shutdown handler
            import atexit
            atexit.register(lambda: stop_all_containers(CONTAINER_NAME_PREFIX))
        
        self.config = config
        self.status_callback = status_callback
        self.sid = sid
        self.plugins = plugins or []
        self.env_vars = env_vars or {}
        self.headless_mode = headless_mode
        
        self._host_port = -1
        self._container_port = -1
        self._vscode_port = -1
        self._app_ports: List[int] = []
        
        # Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            raise DockerConnectionError(f"Failed to connect to Docker: {e}")
        
        # Container
        self.container: Optional[Container] = None
        self.container_name = f"{CONTAINER_NAME_PREFIX}{sid}"
        
        if attach_to_existing:
            self._attach_to_existing_container()
        else:
            self._create_container()
    
    def _attach_to_existing_container(self):
        """Attach to an existing container."""
        try:
            containers = self.docker_client.containers.list(
                all=True, 
                filters={"name": self.container_name}
            )
            
            if not containers:
                raise AgentRuntimeNotFoundError(
                    f"Container {self.container_name} not found"
                )
            
            self.container = containers[0]
            
            # Check if container is running
            if self.container.status != "running":
                self.container.start()
                logger.info(f"Started container: {self.container.name}")
            
            # Get port mappings
            container_info = self.docker_client.api.inspect_container(self.container.id)
            port_bindings = container_info["NetworkSettings"]["Ports"]
            
            # Extract port mappings
            for container_port, host_bindings in port_bindings.items():
                if not host_bindings:
                    continue
                
                port = int(container_port.split("/")[0])
                host_port = int(host_bindings[0]["HostPort"])
                
                if port == self._container_port:
                    self._host_port = host_port
                elif port == 8080:  # VSCode port
                    self._vscode_port = host_port
                else:
                    self._app_ports.append(host_port)
            
            logger.info(f"Attached to container: {self.container.name}")
            
        except docker.errors.NotFound:
            raise AgentRuntimeNotFoundError(
                f"Container {self.container_name} not found"
            )
        except Exception as e:
            raise DockerConnectionError(f"Failed to attach to container: {e}")
    
    def _create_container(self):
        """Create a new container."""
        try:
            # Find available ports
            self._host_port = find_available_tcp_port(
                EXECUTION_SERVER_PORT_RANGE[0], 
                EXECUTION_SERVER_PORT_RANGE[1]
            )
            self._container_port = 8000  # Default port for the execution server
            
            self._vscode_port = find_available_tcp_port(
                VSCODE_PORT_RANGE[0], 
                VSCODE_PORT_RANGE[1]
            )
            
            # App ports
            app_port_1 = find_available_tcp_port(
                APP_PORT_RANGE_1[0], 
                APP_PORT_RANGE_1[1]
            )
            app_port_2 = find_available_tcp_port(
                APP_PORT_RANGE_2[0], 
                APP_PORT_RANGE_2[1]
            )
            self._app_ports = [app_port_1, app_port_2]
            
            # Environment variables
            environment = {
                "BACKDOOR_SESSION_ID": self.sid,
                "BACKDOOR_HOST_PORT": str(self._host_port),
                "BACKDOOR_CONTAINER_PORT": str(self._container_port),
                "BACKDOOR_VSCODE_PORT": str(self._vscode_port),
                "BACKDOOR_APP_PORT_1": str(app_port_1),
                "BACKDOOR_APP_PORT_2": str(app_port_2),
                "BACKDOOR_HEADLESS": str(self.headless_mode).lower(),
            }
            
            # Add user-provided environment variables
            environment.update(self.env_vars)
            
            # Port bindings
            ports = {
                f"{self._container_port}/tcp": self._host_port,
                "8080/tcp": self._vscode_port,
                f"{app_port_1}/tcp": app_port_1,
                f"{app_port_2}/tcp": app_port_2,
            }
            
            # Volumes
            volumes = {
                f"backdoor-volume-{self.sid}": {
                    "bind": "/workspace",
                    "mode": "rw"
                }
            }
            
            # Create and start the container
            self.container = self.docker_client.containers.run(
                image=self.config.docker.image,
                name=self.container_name,
                detach=True,
                environment=environment,
                ports=ports,
                volumes=volumes,
                network=self.config.docker.network,
                restart_policy={"Name": "unless-stopped"},
            )
            
            logger.info(f"Created container: {self.container.name}")
            
            # Wait for container to be ready
            self._wait_for_container_ready()
            
        except docker.errors.ImageNotFound:
            raise DockerNotFoundError(
                f"Docker image {self.config.docker.image} not found"
            )
        except docker.errors.APIError as e:
            raise DockerConnectionError(f"Docker API error: {e}")
        except Exception as e:
            raise DockerConnectionError(f"Failed to create container: {e}")
    
    def _wait_for_container_ready(self, timeout: int = 60):
        """Wait for the container to be ready."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if container is running
                self.container.reload()
                if self.container.status != "running":
                    raise DockerConnectionError(
                        f"Container {self.container.name} is not running"
                    )
                
                # Check if execution server is ready
                url = f"http://localhost:{self._host_port}/health"
                response = httpx.get(url, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"Container {self.container.name} is ready")
                    return
                
            except httpx.RequestError:
                # Server not ready yet, wait and retry
                time.sleep(1)
                continue
            
            except Exception as e:
                logger.error(f"Error checking container readiness: {e}")
                time.sleep(1)
                continue
        
        raise DockerTimeoutError(
            f"Timeout waiting for container {self.container.name} to be ready"
        )
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command in the container.
        
        Args:
            command: The command to execute.
            
        Returns:
            The command execution result.
        """
        if not self.container:
            raise AgentRuntimeNotFoundError("Container not found")
        
        try:
            # Execute command in container
            exec_result = self.container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                demux=True,
            )
            
            stdout, stderr = exec_result.output
            exit_code = exec_result.exit_code
            
            return {
                "stdout": stdout.decode("utf-8") if stdout else "",
                "stderr": stderr.decode("utf-8") if stderr else "",
                "exit_code": exit_code,
            }
            
        except docker.errors.APIError as e:
            raise DockerConnectionError(f"Docker API error: {e}")
        except Exception as e:
            raise DockerConnectionError(f"Failed to execute command: {e}")
    
    def stop(self):
        """Stop the container."""
        if not self.container:
            return
        
        try:
            self.container.stop(timeout=5)
            logger.info(f"Stopped container: {self.container.name}")
        except Exception as e:
            logger.error(f"Error stopping container {self.container.name}: {e}")
    
    def restart(self):
        """Restart the container."""
        if not self.container:
            raise AgentRuntimeNotFoundError("Container not found")
        
        try:
            self.container.restart(timeout=5)
            logger.info(f"Restarted container: {self.container.name}")
            
            # Wait for container to be ready
            self._wait_for_container_ready()
            
        except Exception as e:
            raise DockerConnectionError(f"Failed to restart container: {e}")
    
    def get_logs(self, tail: int = 100) -> str:
        """Get container logs.
        
        Args:
            tail: Number of lines to return from the end of the logs.
            
        Returns:
            The container logs.
        """
        if not self.container:
            raise AgentRuntimeNotFoundError("Container not found")
        
        try:
            logs = self.container.logs(
                stdout=True,
                stderr=True,
                tail=tail,
            ).decode("utf-8")
            
            return logs
            
        except Exception as e:
            raise DockerConnectionError(f"Failed to get logs: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get container status.
        
        Returns:
            The container status.
        """
        if not self.container:
            return {"status": "not_found"}
        
        try:
            self.container.reload()
            
            return {
                "status": self.container.status,
                "id": self.container.id,
                "name": self.container.name,
                "image": self.container.image.tags[0] if self.container.image.tags else "",
                "created": self.container.attrs["Created"],
                "host_port": self._host_port,
                "container_port": self._container_port,
                "vscode_port": self._vscode_port,
                "app_ports": self._app_ports,
            }
            
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return {"status": "error", "error": str(e)}