# Этап 1: Сборка React-приложения
FROM node:18-alpine as builder

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json (или yarn.lock)
COPY package*.json ./
# Если вы используете yarn, замените следующую строку на COPY yarn.lock ./

# Устанавливаем зависимости
# Если вы используете yarn, замените npm install на yarn install
RUN npm install --legacy-peer-deps

# Копируем остальной код приложения
COPY . .

# Собираем приложение для production
RUN npm run build

# Этап 2: Сервер для раздачи статики (Nginx)
FROM nginx:1.25-alpine

# Копируем собранные статические файлы из этапа сборки
COPY --from=builder /app/build /usr/share/nginx/html

# Копируем конфигурацию Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт 80 для Nginx
EXPOSE 80

# Запускаем Nginx
CMD ["nginx", "-g", "daemon off;"]
