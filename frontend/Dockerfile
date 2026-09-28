FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
# Dev server: this project is meant to be run locally.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
