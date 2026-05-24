FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

ENV AGENT_RUNNER_PORT=4000

EXPOSE 4000

CMD ["npm", "start"]
