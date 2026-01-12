# Установка и развертывание Nextcloud для хранения и работы с файлами

Nextcloud — это бесплатная платформа для хранения файлов в облаке, аналог Dropbox или Google Drive, но с собственным сервером. Она позволяет синхронизировать файлы, делиться ими, редактировать документы онлайн и многое другое. Эта инструкция поможет установить Nextcloud на сервер (Ubuntu 22.04) с помощью Docker Compose для простоты и переносимости.

## Предварительные требования
- Сервер с Ubuntu 22.04 (или WSL Ubuntu на Windows).
- Доступ по SSH (если сервер удалённый).
- Домен, направленный на IP сервера (для HTTPS).
- Docker и Docker Compose установлены (если нет, см. шаг 1).
- Базовые знания командной строки.

## Пошаговая инструкция по установке

### Шаг 1: Установка Docker и Docker Compose
Если Docker не установлен, выполните:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавление репозитория Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавление пользователя в группу docker (для запуска без sudo)
sudo usermod -aG docker $USER

# Перезагрузка или перелогин для применения изменений
```

### Шаг 2: Создание папки проекта
Перейдите в папку nextcloud (или создайте, если нет):
```bash
cd /home/steve/OdooApps/odoo_projects/dino24_addons/dino_erp/nextcloud
```

### Шаг 3: Создание файла docker-compose.yml
Создайте файл `docker-compose.yml` с конфигурацией для Nextcloud, MariaDB и Traefik (для авто-HTTPS). Замените PLACEHOLDERS:
- `DOMAIN.example.com` — ваш домен.
- `EMAIL@example.com` — email для Let's Encrypt.
- Пароли: придумайте сильные (минимум 12 символов, с буквами, цифрами, символами).

```yaml
version: "3.8"
services:
  # Traefik для прокси и авто-TLS
  traefik:
    image: traefik:2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=EMAIL@example.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
      - "--log.level=INFO"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    restart: unless-stopped

  # База данных MariaDB
  db:
    image: mariadb:10.11
    environment:
      MYSQL_ROOT_PASSWORD: CHANGE_ROOT_PASSWORD
      MYSQL_DATABASE: nextcloud
      MYSQL_USER: nextcloud
      MYSQL_PASSWORD: CHANGE_DB_PASSWORD
    volumes:
      - db_data:/var/lib/mysql
    restart: unless-stopped

  # Nextcloud приложение
  app:
    image: nextcloud:28-apache
    depends_on:
      - db
    environment:
      MYSQL_HOST: db
      MYSQL_DATABASE: nextcloud
      MYSQL_USER: nextcloud
      MYSQL_PASSWORD: CHANGE_DB_PASSWORD
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

### Шаг 4: Настройка сервера и запуск
```bash
# Создание папки для сертификатов и установка прав
mkdir -p ./letsencrypt
sudo chown 1000:1000 ./letsencrypt || true

# Открытие портов в брандмауэре (ufw)
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Запуск контейнеров
docker compose up -d
```

### Шаг 5: Первичная настройка Nextcloud
- Откройте браузер и перейдите на `https://DOMAIN.example.com` (HTTPS должен заработать автоматически через Traefik и Let's Encrypt).
- Создайте учётную запись администратора (имя пользователя, пароль).
- На странице настройки БД укажите:
  - Тип: MySQL/MariaDB
  - Хост: db
  - База: nextcloud
  - Пользователь: nextcloud
  - Пароль: CHANGE_DB_PASSWORD (как в compose).
- Нажмите "Установить".

После установки вы увидите дашборд Nextcloud.

## Работа с файлами в Nextcloud
- **Загрузка файлов**: В веб-интерфейсе нажмите "Файлы" > "Загрузить" или перетащите файлы.
- **Синхронизация**: Установите клиент Nextcloud на ПК/мобильное (скачайте с nextcloud.com). Введите URL сервера и учётные данные.
- **Дележка**: Выберите файл > "Поделиться" > укажите пользователей или ссылку.
- **Редактирование**: Для документов установите OnlyOffice или Collabora (через приложения в Nextcloud).
- **Приложения**: В "Приложения" установите дополнительные модули (например, для календаря, контактов).

## Обслуживание и безопасность
- **Обновления**: Регулярно обновляйте образы: `docker compose pull && docker compose up -d`.
- **Бэкапы**: Копируйте volumes (db_data, nextcloud_data) с помощью `docker run --rm -v nextcloud_db_data:/data -v $(pwd):/backup alpine tar czf /backup/db_backup.tar.gz -C /data .`.
- **Безопасность**: Используйте сильные пароли, включите 2FA в настройках, мониторьте логи (`docker compose logs`).
- **Траблшутинг**: Если не запускается, проверьте логи: `docker compose logs -f app`. Убедитесь, что порты открыты и домен корректен.

Если возникнут проблемы или нужен вариант без Docker, уточните.