FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy dependency list
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application source code
COPY . .

# Expose Vite dev server default port
EXPOSE 5173

# Start development server
CMD ["npm", "run", "dev"]
