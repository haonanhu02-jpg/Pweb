FROM node:24-alpine

WORKDIR /app

COPY web/package*.json ./
RUN npm install

COPY web ./

ENV VITE_API_BASE_URL=http://localhost:8000

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
