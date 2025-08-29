# LinguaSynth

# Setup
LinguaSynth uses a Makefile to start up its docker containers. See the list of available commands bellow

## Start everything up in attached terminal
command: `make start`
## Start everything up in detached terminal
command: `make start-d`
## Shutdown all docker containers 
command: `make down`
## Shutdown all docker containers and clean up volumes
command: `make down-f`
## delete all docker images on the machine. 
command: `make images_delete`
## Get a list of all docker images that are currently on the machine.
command: `make get_images`