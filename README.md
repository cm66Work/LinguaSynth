# LinguaSynth

# Setup
LinguaSynth uses a Makefile to start up its docker containers. See the list of available commands bellow

- command: `make start`
  - Start everything up in attached terminal
- command: `make start-d`
  - Start everything up in detached terminal
- command: `make down`
  - Shutdown all docker containers 
- command: `make down-f`
  - Shutdown all docker containers and clean up volumes
- command: `make images_delete`
  - Delete all docker images on the machine. 
- command: `make get_images`
  - Get a list of all docker images that are currently on the machine.