FROM node:18.12-slim

WORKDIR /var/ng/project
# install angular cli
RUN npm install -g @angular/cli@14.1.0
ENV NG_CLI_ANALYTICS=false
RUN ng version

# install dependencies
COPY ["./code/package.json", "./code/package-lock.json", "./"]
RUN npm ci

# build
COPY ./code .
RUN ng build

# copy build files to /var/ng
WORKDIR /var/ng
RUN mv ./project/dist ./dist
RUN rm -rf ./project
RUN mv ./dist/* .
RUN rm -rf ./dist

# keep container running
CMD tailf /dev/null
