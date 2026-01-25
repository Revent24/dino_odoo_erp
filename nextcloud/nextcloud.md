# Установка и развертывание Nextcloud на Ubuntu 22.04 с Docker Compose

Nextcloud — это бесплатная платформа для облачного хранения файлов. Эта инструкция поможет установить Nextcloud с использованием Docker Compose.

## Требования
- Ubuntu 22.04 (или WSL Ubuntu).
- Установленные Docker и Docker Compose.
- Домен, направленный на сервер (для HTTPS).

## Шаги установки

### 1. Установка Docker и Docker Compose
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавление репозитория Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
```
Перезагрузите систему или выполните повторный вход в систему.

### 2. Создание проекта
```bash
mkdir -p ~/nextcloud && cd ~/nextcloud
```

### 3. Создание docker-compose.yml
Создайте файл `docker-compose.yml` со следующим содержимым:
```yaml
version: "3.8"

services:
  traefik:
    image: traefik:2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=EMAIL@example.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: unless-stopped

  db:
    image: mariadb:10.11
    environment:
      MYSQL_ROOT_PASSWORD: strong_root_password
      MYSQL_DATABASE: nextcloud
      MYSQL_USER: nextcloud
      MYSQL_PASSWORD: strong_password
    volumes:
      - db_data:/var/lib/mysql
    restart: unless-stopped

  redis:
    image: redis:alpine
    restart: unless-stopped

  app:
    image: nextcloud:latest
    depends_on:
      - db
      - redis
    ports:
      - "8080:80"  # Проброс порта 8080 на 80
    environment:
      MYSQL_HOST: db
      MYSQL_DATABASE: nextcloud
      MYSQL_USER: nextcloud
      MYSQL_PASSWORD: strong_password
      REDIS_HOST: redis
    volumes:
      - nextcloud_data:/var/www/html
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.nextcloud.rule=Host(`DOMAIN.example.com`)" 
      - "traefik.http.routers.nextcloud.entrypoints=websecure"
      - "traefik.http.routers.nextcloud.tls.certresolver=myresolver"
    restart: unless-stopped

volumes:
  db_data:
  nextcloud_data:
```
Замените `DOMAIN.example.com` и `EMAIL@example.com` на ваш домен и email.

### 4. Запуск контейнеров
После перехода в директорию с файлом `docker-compose.yml` выполните следующую команду для запуска контейнеров:
```bash
docker-compose up -d
```
Эта команда запустит все сервисы, указанные в файле `docker-compose.yml`, в фоновом режиме.

### 5. Настройка Nextcloud
1. Перейдите на `https://DOMAIN.example.com`.
2. Создайте учётную запись администратора.
3. Укажите настройки базы данных:
   - Тип: MySQL/MariaDB
   - Хост: db
   - База: nextcloud
   - Пользователь: nextcloud
   - Пароль: strong_password
4. Нажмите "Установить".

### 6. Рекомендации
- **Обновления**: `docker compose pull && docker compose up -d`
- **Бэкапы**: Сохраняйте volumes (db_data, nextcloud_data).
- **Безопасность**: Используйте 2FA, проверяйте логи: `docker compose logs`.

### 7. Поиск существующих файлов конфигурации
Если вы хотите найти уже существующие файлы `docker-compose.yml` или `compose.yml` на вашем сервере, выполните следующую команду:
```bash
find ~ -type f \( -name "docker-compose.yml" -o -name "compose.yml" \) 2>/dev/null
```
Эта команда выполнит поиск в домашней директории и выведет пути к найденным файлам. Если файлы отсутствуют, создайте их, следуя шагу 3.

### 8. Переход в найденную директорию
После выполнения команды поиска, если вы нашли нужный файл конфигурации, перейдите в соответствующую директорию. Например:
```bash
cd /home/steve/nextcloud_stack
```
Это позволит вам работать с найденной конфигурацией и запускать контейнеры из этой директории.

### 9. Настройка Nextcloud после загрузки контейнеров
После успешного запуска контейнеров выполните следующие команды для настройки локального кэша и подключения к Redis:

1. Настройка локального кэша:
```bash
docker exec -u www-data nextcloud_stack_app_1 php occ config:system:set memcache.local --value '\\OC\\Memcache\\APCu'
```

2. Настройка блокировок файлов через Redis (чтобы избежать конфликтов с Odoo):
```bash
docker exec -u www-data nextcloud_stack_app_1 php occ config:system:set memcache.locking --value '\\OC\\Memcache\\Redis'
```

3. Указание параметров подключения к Redis:
```bash
docker exec -u www-data nextcloud_stack_app_1 php occ config:system:set redis --value '{"host":"redis","port":6379}' --type json
```