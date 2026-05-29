FROM node:22-alpine

WORKDIR /app

# Install dependencies as a separate layer
COPY package.json package-lock.json ./
RUN npm ci

# Source is bind-mounted at runtime; this COPY is for CI/production use
COPY . .

CMD ["npm", "run", "dev"]
