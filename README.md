# Foodgram

Проект foodgram - сервис для публикации и обмена рецептами.

## Инструкция для ревьюера

### Запуск проекта

1. Клонировать репозиторий и перейти в него:
```bash
git clone https://github.com/ivantishko/foodgram-st.git
cd foodgram-st
```

2. Создать файл .env в директории infra/ с необходимыми переменными окружения:
```bash
touch infra/.env
```

3. Заполнить файл .env следующими переменными:
```
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432
SECRET_KEY=your-secret-key
DEBUG=False
DOCKER_USERNAME=your-dockerhub-username
```

4. Запустить docker-compose:
```bash
cd infra
docker-compose -f docker-compose.yml up --build
```

5. После запуска контейнеров будут выполнены следующие шаги автоматически:
   - Применение миграций Django
   - Загрузка ингредиентов в базу данных
   - Сбор статических файлов

6. Проверить статус контейнеров:
```bash
docker-compose ps
```

7. Проверить логи, если что-то пошло не так:
```bash
docker-compose logs backend
```

8. Доступ к проекту:
   - Веб-интерфейс: http://localhost
   - API документация: http://localhost/api/docs/
   - Админ-панель: http://localhost/admin/

### Тестовый аккаунт администратора
Логин: admin@example.com
Пароль: admin

### Остановка проекта
```bash
docker-compose down
```

## Настройка CI/CD и автоматической публикации образов

Для автоматической проверки, сборки и публикации Docker-образов используется GitHub Actions.

### Настройка секретов для CI/CD

Для корректной работы CI/CD необходимо добавить следующие секреты в репозиторий:

1. `DOCKER_USERNAME` - ваше имя пользователя на Docker Hub
2. `DOCKER_PASSWORD` - ваш пароль или токен для Docker Hub

Добавление секретов:
1. Перейдите в настройки репозитория
2. Выберите "Secrets and variables" -> "Actions"
3. Нажмите "New repository secret"
4. Добавьте указанные выше секреты

### Процесс работы CI/CD

При каждом пуше или pull request в ветки main или master автоматически запускаются:

1. Проверка кода бэкенда с помощью flake8
2. Проверка кода фронтенда с помощью ESLint
3. Сборка и публикация Docker-образов на Docker Hub (только для пушей в main или master)

Образы публикуются с двумя тегами:
- `latest` - всегда указывает на последнюю версию
- `YYYYMMDDHHmmss` - версия с временной меткой для возможности отката

### Ручная публикация образов

Для ручной публикации образов выполните:

```bash
# Войти в Docker Hub
docker login

# Собрать и пометить образы
docker build -t username/foodgram-backend:latest ./backend
docker build -t username/foodgram-frontend:latest ./frontend

# Опубликовать образы
docker push username/foodgram-backend:latest
docker push username/foodgram-frontend:latest
```

## Запуск проекта

### Предварительные требования
- Docker
- Docker Compose

### Локальный запуск
```bash
# Клонирование репозитория
git clone <repository-url>
cd foodgram-st

# Запуск контейнеров
docker-compose -f infra/docker-compose.yml up -d

# Проверка логов
docker-compose -f infra/docker-compose.yml logs
```

После запуска сайт будет доступен по адресу http://localhost

Находясь в папке infra, выполните команду docker-compose up. При выполнении этой команды контейнер frontend, описанный в docker-compose.yml, подготовит файлы, необходимые для работы фронтенд-приложения, а затем прекратит свою работу.

По адресу http://localhost изучите фронтенд веб-приложения, а по адресу http://localhost/api/docs/ — спецификацию API.

