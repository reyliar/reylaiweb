FROM node:20-alpine
WORKDIR /app
COPY package.json server.js ./
RUN npm install --omit=dev
EXPOSE 3000
CMD ["npm", "start"]
