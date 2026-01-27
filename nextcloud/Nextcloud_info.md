# **Справочник работы с Nextcloud**

## **Содержание**
1. [Основные понятия](#1-основные-понятия)
   - [File-ID](#file-id)
   - [oc:id](#ocid)
2. [Методы поиска](#2-методы-поиска)
   - [Метод PROPFIND](#метод-propfind)
   - [Метод SEARCH](#метод-search)
3. [Очистка File-ID](#3-очистка-file-id)
   - [Почему необходима очистка?](#почему-необходима-очистка)
   - [Алгоритм очистки](#алгоритм-очистки)
4. [Реализация на Python](#4-реализация-на-python)
   - [Поиск папки по File-ID](#поиск-папки-по-file-id)
   - [Получение всех папок](#получение-всех-папок)
5. [Рекомендации](#5-рекомендации)
   - [Оптимизация запросов](#оптимизация-запросов)
   - [Обработка ошибок](#обработка-ошибок)
   - [Сохранение данных](#сохранение-данных)
6. [Поиск файлов по File-ID](#6-поиск-файлов-по-file-id)
   - [Вариант 1: Поиск файла по File-ID](#вариант-1-поиск-файла-по-file-id)
7. [Операции с файлами](#7-операции-с-файлами)
   - [Создание файла](#создание-файла)
   - [Загрузка файла](#загрузка-файла)
   - [Перемещение файла](#перемещение-файла)
   - [Переименование файла](#переименование-файла)
   - [Удаление файла](#удаление-файла)
   - [Получение информации о файле](#получение-информации-о-файле)
8. [Создание защищенной древовидной структуры в Nextcloud с интеграцией в Odoo](#8-создание-защищенной-древовидной-структуры-в-nextcloud-с-интеграцией-в-odoo)
9. [Групповые папки (Group Folders)](##-групповые-папки-group-folders)

---

## **1. Основные понятия**

### **File-ID**
- **File-ID** — это уникальный числовой идентификатор объекта (папки или файла) в базе данных Nextcloud.
- **Особенности**:
  - File-ID остается неизменным при переименовании или перемещении объекта.
  - Используется для надежной привязки объектов в интеграциях.

### **oc:id**
- **oc:id** — это глобально уникальный строковый идентификатор, включающий File-ID и суффикс инстанса сервера.
- **Пример**: `00000063oczn5x60nrdu`.
- **Использование**:
  - Не подходит для поиска, но может быть полезен для идентификации объекта.

---

## **2. Методы поиска**

### **Метод PROPFIND**
- Используется для получения данных обо всех объектах внутри известной папки.
- **Особенности**:
  - Заголовок `Depth: 1` возвращает метаданные самой папки и её непосредственных детей.
  - Тело запроса должно явно запрашивать свойства, такие как `oc:fileid` и `d:displayname`.

**Пример XML-запроса**:
```xml
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop>
    <oc:fileid />
    <d:displayname />
  </d:prop>
</d:propfind>
```

---

### **Метод SEARCH**
- Используется для поиска объектов по File-ID или другим свойствам.
- **Особенности**:
  - Поддерживает фильтрацию на стороне сервера.
  - Глубина поиска (`Depth`) может быть установлена в `infinity` для поиска по всему диску.

**Пример XML-запроса для поиска по File-ID**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:basicsearch>
    <d:select>
      <d:prop>
        <d:displayname/>
        <oc:fileid/>
      </d:prop>
    </d:select>
    <d:from>
      <d:scope>
        <d:href>/files/username</d:href>
        <d:depth>infinity</d:depth>
      </d:scope>
    </d:from>
    <d:where>
      <d:and>
        <d:eq>
          <d:prop><oc:fileid/></d:prop>
          <d:literal>63</d:literal>
        </d:eq>
        <d:is-collection/>
      </d:and>
    </d:where>
  </d:basicsearch>
</d:searchrequest>
```

---

## **3. Очистка File-ID**

### **Почему необходима очистка?**
- File-ID может быть возвращен сервером в формате `00000063oczn5x60nrdu`.
- Для использования в методе SEARCH необходимо преобразовать его в числовой формат.

### **Алгоритм очистки**
#### **Вариант 1: Фильтрация цифр**
```python
raw_id = "00000259oczn5x60nrdu"
numeric_part = raw_id.split('oc')[0]
clean_id = int(numeric_part)
print(clean_id)  # Результат: 259
```

#### **Вариант 2: Регулярные выражения**
```python
import re
raw_id = "00000259oczn5x60nrdu"
match = re.match(r'^(\d+)', raw_id)
if match:
    clean_id = int(match.group(1))
```

---

## **4. Реализация на Python**

### **Поиск папки по File-ID**
```python
import requests
from lxml import etree

def find_folder_by_id(file_id, username, password):
    base_url = "http://localhost:8080/remote.php/dav/"
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:basicsearch>
        <d:select>
          <d:prop>
            <d:displayname/>
            <oc:fileid/>
          </d:prop>
        </d:select>
        <d:from>
          <d:scope>
            <d:href>/files/{username}</d:href>
            <d:depth>infinity</d:depth>
          </d:scope>
        </d:from>
        <d:where>
          <d:eq>
            <d:prop><oc:fileid/></d:prop>
            <d:literal>{file_id}</d:literal>
          </d:eq>
        </d:where>
      </d:basicsearch>
    </d:searchrequest>"""

    headers = {'Content-Type': 'text/xml'}
    response = requests.request("SEARCH", base_url, data=xml_body, 
                                auth=(username, password), headers=headers)

    if response.status_code == 207:
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        root = etree.fromstring(response.content)
        hrefs = root.xpath('//d:response/d:href/text()', namespaces=ns)
        return hrefs if hrefs else None
    return f"Error: {response.status_code}"
```

---

### **Получение всех папок**
```python
def get_all_folders_with_ids(username, password):
    base_url = "http://localhost:8080/remote.php/dav/"
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:basicsearch>
        <d:select>
          <d:prop><oc:fileid/><d:displayname/></d:prop>
        </d:select>
        <d:from>
          <d:scope>
            <d:href>/files/{username}</d:href>
            <d:depth>infinity</d:depth>
          </d:scope>
        </d:from>
        <d:where><d:is-collection/></d:where>
      </d:basicsearch>
    </d:searchrequest>"""

    response = requests.request("SEARCH", base_url, data=xml_body, 
                                auth=(username, password), headers={'Content-Type': 'text/xml'})
    
    ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
    root = etree.fromstring(response.content)
    results = []
    for resp in root.xpath('//d:response', namespaces=ns):
        results.append({
            'name': resp.xpath('.//d:displayname/text()', namespaces=ns),
            'id': resp.xpath('.//oc:fileid/text()', namespaces=ns),
            'path': resp.xpath('./d:href/text()', namespaces=ns)
        })
    return results
```

---

## **5. Рекомендации**

### **Оптимизация запросов**
- Используйте `Depth: 0` для получения данных о конкретной папке.
- Для поиска по всему диску используйте `Depth: infinity`.

### **Обработка ошибок**
- Если метод SEARCH возвращает пустой результат, выполните сканирование файлов через `occ files:scan --all`.

### **Сохранение данных**
- Сохраняйте File-ID как целое число (Integer) для надежной привязки объектов.

---

## **Примеры функций поиска по File-ID**

### **Пример 1: Поиск пути к папке по File-ID**
```python
import requests
from lxml import etree

def get_folder_path_by_file_id(file_id, username, password):
    base_url = "http://localhost:8080/remote.php/dav/"
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:basicsearch>
        <d:select>
          <d:prop>
            <d:displayname/>
            <oc:fileid/>
            <d:resourcetype/>
          </d:prop>
        </d:select>
        <d:from>
          <d:scope>
            <d:href>/files/{username}</d:href>
            <d:depth>infinity</d:depth>
          </d:scope>
        </d:from>
        <d:where>
          <d:eq>
            <d:prop><oc:fileid/></d:prop>
            <d:literal>{file_id}</d:literal>
          </d:eq>
        </d:where>
      </d:basicsearch>
    </d:searchrequest>"""

    headers = {'Content-Type': 'text/xml'}
    response = requests.request("SEARCH", base_url, data=xml_body, auth=(username, password), headers=headers)

    if response.status_code == 207:
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        root = etree.fromstring(response.content)
        hrefs = root.xpath('//d:response/d:href/text()', namespaces=ns)
        return hrefs[0] if hrefs else None
    else:
        return f"Error: {response.status_code}"

# Пример использования
username = "user"
password = "password"
file_id = 63
folder_path = get_folder_path_by_file_id(file_id, username, password)
print(f"Путь к папке: {folder_path}")
```

### **Пример 2: Получение всех объектов с их File-ID**
```python
def get_all_objects_with_file_ids(username, password):
    base_url = "http://localhost:8080/remote.php/dav/"
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:basicsearch>
        <d:select>
          <d:prop>
            <d:displayname/>
            <oc:fileid/>
            <d:resourcetype/>
          </d:prop>
        </d:select>
        <d:from>
          <d:scope>
            <d:href>/files/{username}</d:href>
            <d:depth>infinity</d:depth>
          </d:scope>
        </d:from>
      </d:basicsearch>
    </d:searchrequest>"""

    headers = {'Content-Type': 'text/xml'}
    response = requests.request("SEARCH", base_url, data=xml_body, auth=(username, password), headers=headers)

    if response.status_code == 207:
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        root = etree.fromstring(response.content)
        results = []
        for resp in root.xpath('//d:response', namespaces=ns):
            results.append({
                'name': resp.xpath('.//d:displayname/text()', namespaces=ns)[0],
                'id': resp.xpath('.//oc:fileid/text()', namespaces=ns)[0],
                'path': resp.xpath('./d:href/text()', namespaces=ns)[0]
            })
        return results
    else:
        return f"Error: {response.status_code}"

# Пример использования
username = "user"
password = "password"
objects = get_all_objects_with_file_ids(username, password)
for obj in objects:
    print(f"Имя: {obj['name']}, ID: {obj['id']}, Путь: {obj['path']}")
```

---

## **6. Поиск файлов по File-ID**

### **Вариант 1: Поиск файла по File-ID**
```python
import requests
from lxml import etree

def find_file_by_id(file_id, username, password):
    base_url = "http://localhost:8080/remote.php/dav/"
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <d:searchrequest xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:basicsearch>
        <d:select>
          <d:prop>
            <d:displayname/>
            <oc:fileid/>
            <d:getcontenttype/>
            <d:getcontentlength/>
            <d:getlastmodified/>
          </d:prop>
        </d:select>
        <d:from>
          <d:scope>
            <d:href>/files/{username}</d:href>
            <d:depth>infinity</d:depth>
          </d:scope>
        </d:from>
        <d:where>
          <d:eq>
            <d:prop><oc:fileid/></d:prop>
            <d:literal>{file_id}</d:literal>
          </d:eq>
        </d:where>
      </d:basicsearch>
    </d:searchrequest>"""

    headers = {'Content-Type': 'text/xml'}
    response = requests.request("SEARCH", base_url, data=xml_body, auth=(username, password), headers=headers)

    if response.status_code == 207:
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        root = etree.fromstring(response.content)
        file_info = {
            'name': root.xpath('//d:displayname/text()', namespaces=ns),
            'id': root.xpath('//oc:fileid/text()', namespaces=ns),
            'type': root.xpath('//d:getcontenttype/text()', namespaces=ns),
            'size': root.xpath('//d:getcontentlength/text()', namespaces=ns),
            'last_modified': root.xpath('//d:getlastmodified/text()', namespaces=ns)
        }
        return file_info
    else:
        return f"Error: {response.status_code}"
```

---

## **7. Операции с файлами**

### **Создание файла**
```python
import requests

def create_file(file_path, content, username, password):
    base_url = f"http://localhost:8080/remote.php/dav/files/{username}/{file_path}"
    headers = {'Content-Type': 'application/octet-stream'}
    response = requests.put(base_url, data=content, auth=(username, password), headers=headers)

    if response.status_code == 201:
        return "Файл успешно создан."
    else:
        return f"Ошибка: {response.status_code}"
```

---

### **Загрузка файла**
```python
import requests

def upload_file(local_file_path, remote_file_path, username, password):
    base_url = f"http://localhost:8080/remote.php/dav/files/{username}/{remote_file_path}"
    with open(local_file_path, 'rb') as file:
        response = requests.put(base_url, data=file, auth=(username, password))

    if response.status_code == 201:
        return "Файл успешно загружен."
    else:
        return f"Ошибка: {response.status_code}"
```

---

### **Перемещение файла**
```python
import requests

def move_file(source_path, destination_path, username, password):
    base_url = f"http://localhost:8080/remote.php/dav/files/{username}/{source_path}"
    headers = {'Destination': f"http://localhost:8080/remote.php/dav/files/{username}/{destination_path}"}
    response = requests.request("MOVE", base_url, auth=(username, password), headers=headers)

    if response.status_code in [201, 204]:
        return "Файл успешно перемещен."
    else:
        return f"Ошибка: {response.status_code}"
```

---

### **Переименование файла**
```python
import requests

def rename_file(file_path, new_name, username, password):
    destination_path = "/".join(file_path.split("/")[:-1] + [new_name])
    return move_file(file_path, destination_path, username, password)
```

---

### **Удаление файла**
```python
import requests

def delete_file(file_path, username, password):
    base_url = f"http://localhost:8080/remote.php/dav/files/{username}/{file_path}"
    response = requests.delete(base_url, auth=(username, password))

    if response.status_code == 204:
        return "Файл успешно удален."
    else:
        return f"Ошибка: {response.status_code}"
```

---

### **Получение информации о файле**
```python
import requests
from lxml import etree

def get_file_info(file_path, username, password):
    base_url = f"http://localhost:8080/remote.php/dav/files/{username}/{file_path}"
    headers = {'Depth': '0'}
    response = requests.request("PROPFIND", base_url, auth=(username, password), headers=headers)

    if response.status_code == 207:
        ns = {'d': 'DAV:', 'oc': 'http://owncloud.org/ns'}
        root = etree.fromstring(response.content)
        file_info = {
            'name': root.xpath('//d:displayname/text()', namespaces=ns),
            'id': root.xpath('//oc:fileid/text()', namespaces=ns),
            'type': root.xpath('//d:getcontenttype/text()', namespaces=ns),
            'size': root.xpath('//d:getcontentlength/text()', namespaces=ns),
            'last_modified': root.xpath('//d:getlastmodified/text()', namespaces=ns)
        }
        return file_info
    else:
        return f"Ошибка: {response.status_code}"
```

---

## **8. Создание защищенной древовидной структуры в Nextcloud с интеграцией в Odoo**

Для реализации вашей задачи — создания защищенной древовидной структуры в Nextcloud/OpenCloud с интеграцией в Odoo — необходимо использовать комбинацию системных идентификаторов, специальных заголовков WebDAV и продвинутых инструментов контроля доступа.

### 1. Автоматическое создание иерархии (Odoo -> Nextcloud)
Чтобы создать структуру `Категория/Год/Месяц/Дата+Проект` одним запросом, используйте метод **PUT** или **MKCOL** со специальным заголовком:

- **Заголовок:** **`X-NC-WebDAV-AutoMkcol: 1`**.
- **Действие:** Этот заголовок заставляет сервер автоматически создавать всю цепочку промежуточных папок (год, месяц и т. д.), если они отсутствуют.
- **Фиксация:** После создания папки проекта Оdoo **обязательно** должна получить и сохранить в своей базе данных заголовок **`OC-FileId`** из ответа сервера. Этот идентификатор является числовым (**Integer**) и остается неизменным, даже если путь к папке в будущем изменится.

### 2. Обеспечение неизменности структуры (Защита от пользователей)
Для того чтобы пользователи могли наполнять папки, но не могли их удалять или перемещать, рекомендуется использовать один из двух механизмов Nextcloud:

#### Вариант А: Приложение Group Folders (Групповые папки) — РЕКОМЕНДУЕТСЯ
Это приложение позволяет создавать общие папки с расширенными списками управления доступом (**Advanced ACL**).
- **Настройка:** Оdoo создает папку внутри групповой директории и через API устанавливает для пользователей/групп специфические права.
- **Права доступа:** Вы можете запретить права на **удаление (Deletable)**, **переименование (Renameable)** и **перемещение (Moveable)** для самой папки, но разрешить **запись (Writable)** и **создание (Creatable)** для её содержимого.

#### Вариант Б: File Access Control (Flow) + Теги
Если групповые папки не подходят, можно использовать систему автоматического тегирования и контроля доступа.
1. **Тегирование:** Odoo при создании присваивает папке системный **restricted** (ограниченный) тег (например, `System_Folder`), который обычный пользователь не может снять.
2. **Правило Flow:** В настройках Nextcloud создается правило: «Если объект помечен тегом `System_Folder`, заблокировать для него операции **DELETE** и **MOVE** для всех, кроме администратора».

### 3. Надежная связь Odoo с папками (Dynamic Path Search)
Даже если структура защищена, всегда существует риск административных изменений. Чтобы Odoo никогда не теряла связь с папкой проекта:
- Не полагайтесь на жестко прописанные пути вида `/remote.php/dav/files/user/Category/2024/...`.
- При необходимости совершить действие с папкой, Odoo должна отправить запрос методом **SEARCH**, используя сохраненный числовой **fileid**.
- Сервер вернет **актуальный путь (href)**, по которому Оdoo сможет корректно обратиться к ресурсу.

### Резюме для разработчика Odoo:
1. **Создание:** `PUT` с заголовком `X-NC-WebDAV-AutoMkcol: 1`.
2. **Хранение:** Сохраняйте в БД Odoo числовой `fileid` из заголовка ответа `OC-FileId`.
3. **Защита:** Используйте **Group Folders** с включенными ACL для детального запрета перемещения папок при сохранении прав на манипуляцию файлами внутри них.
4. **Синхронизация:** Для получения текущего пути папки всегда используйте метод **SEARCH** по `fileid`.

---

### 4. Техническая гарантия доступа: Использование File-ID
Главный риск при работе со стандартными путями WebDAV (например, `/remote.php/dav/files/user/folder`) заключается в том, что если пользователь переименует или переместит папку вручную, путь изменится, и ваше приложение получит ошибку 404.

- **Неизменяемый идентификатор:** Каждому объекту при создании присваивается системный идентификатор **`oc:fileid`** (например, `63`), который **никогда не меняется**, даже если папку переместили по всему диску или переименовали.
- **Динамический поиск пути:** Вместо хранения жестких путей ваше приложение должно хранить в своей базе данных числовой `fileid`. Перед каждой операцией приложение отправляет запрос методом **`SEARCH`**, чтобы получить текущий актуальный путь (`href`) по этому ID.
- **Создание структуры:** Чтобы гарантировать целостность структуры при первой загрузке, используйте заголовок **`X-NC-WebDAV-AutoMkcol: 1`**. Он заставляет сервер автоматически создавать всю цепочку недостающих родительских папок, что исключает ошибки при создании глубоко вложенных директорий.

### 5. Административная защита: Ограничение прав доступа
Чтобы пользователи не могли самостоятельно удалять или перемещать структуру, созданную приложением, используйте следующие инструменты:

- **Расширенные списки управления доступом (Advanced ACL):** Если используется приложение **Group Folders**, вы можете включить поддержку ACL (`nc:acl-enabled`) и явно запретить права на удаление (`Deletable`), переименование (`Renameable`) и перемещение (`Moveable`) для определенных групп пользователей.
- **File Access Control (Flow):** Вы можете настроить правила автоматической блокировки доступа. Например, можно назначить папкам приложения специальный **restricted** (ограниченный) тег, а через Flow создать правило: «если объект помечен этим тегом, запретить операцию DELETE для всех, кроме администратора».
- **Режим Read-Only для внешних хранилищ:** Если структура папок создается на подключенном внешнем хранилище (External Storage), в настройках монтирования можно установить флаг **«Read only»**. Это сделает невозможным любое изменение данных (включая удаление и перемещение) через интерфейс Nextcloud для всех пользователей.

### 6. Рекомендованный алгоритм действий:
1. **Создавайте папки под учетной записью администратора**, используя `App Password` для авторизации скрипта.
2. **Сохраняйте полученный `oc:fileid`** сразу после создания папки (он возвращается в заголовке `OC-FileId` ответа сервера).
3. **Установите права доступа** через Share API с параметром `permissions=1` (только чтение) для всех пользователей, которым нужна эта структура.
4. **Для максимальной надежности используйте Group Folders** с включенными ACL, чтобы запретить перемещение даже тем пользователям, у которых есть права на запись файлов внутри этих папок.

Такой подход дает **двойную гарантию**: динамический поиск через `SEARCH` защищает логику приложения от смены путей, а настройки ACL и Flow защищают саму структуру от физического удаления пользователями.

---

### 7. Автоматизация работы с Групповыми папками через Python и Odoo

Автоматизация работы с **Групповыми папками (Group Folders)** через Python и Odoo требует сочетания двух интерфейсов: **OCS API** (для администрирования самих папок и прав доступа) и **WebDAV** (для управления структурой файлов внутри них).

Ниже приведено руководство по реализации такой системы:

#### 1. Администрирование Групповых папок через API
Для создания самой "корневой" групповой папки и управления её настройками (квоты, группы доступа) используется **OCS API** приложения Group Folders. Хотя основные источники делают упор на команды `occ` (например, `occ groupfolders:create`), для Odoo удобнее использовать HTTP-запросы.

*   **Авторизация:** Используйте **App Password**. Обязательно добавляйте заголовок `OCS-APIRequest: true` во все запросы.
*   **Создание папки:** Отправьте POST-запрос на эндпоинт `/ocs/v2.php/apps/groupfolders/folders`. В ответ вы получите `nc:group-folder-id`.
*   **Настройка прав (ACL):** Чтобы гарантировать неизменность структуры, через API или WebDAV-свойство `<nc:acl-enabled>1</nc:acl-enabled>` включите расширенные права. Это позволит запретить перемещение (`Moveable`) и переименование (`Renameable`) папок для обычных пользователей.

#### 2. Автоматическое создание иерархии (Python + WebDAV)
Когда Odoo создает проект, вам нужно мгновенно выстроить дерево `Категория/Год/Месяц/Дата+Проект`. 

*   **Оптимизация запросов:** Используйте заголовок **`X-NC-WebDAV-AutoMkcol: 1`**. 
*   **Логика:** При выполнении первого `PUT`-запроса (загрузка пустого файла-метки или реального документа) по полному пути проекта, Nextcloud автоматически создаст все недостающие родительские папки. Это избавляет от необходимости проверять наличие каждой папки (`Категория`, `Год` и т.д.) через `PROPFIND` или создавать их по одной через `MKCOL`.

#### 3. Интеграция и надежность в Odoo (File-ID)
Главный принцип надежной интеграции — **не полагаться на текстовые пути**. 

1.  **Сохранение ID:** Сразу после создания папки проекта в Odoo, скрипт должен извлечь заголовок **`OC-FileId`** из ответа сервера и сохранить его в базе данных Odoo. 
2.  **Динамический поиск:** Если пользователь (администратор) переместит или переименует папку, её текстовый путь изменится, но `fileid` останется прежним. Перед выполнением операций Odoo должна отправить запрос методом **`SEARCH`**, чтобы получить текущий актуальный путь (`href`) по сохраненному ID.
3.  **Формат поиска:** Поиск должен выполняться по свойству `oc:fileid` (тип **Integer**).

#### Пример реализации на Python (requests)
```python
import requests

# Учетные данные (используйте App Password)
auth = ('odoo_bot', 'xxxx-xxxx-xxxx-xxxx')
headers = {
    'OCS-APIRequest': 'true',
    'X-NC-WebDAV-AutoMkcol': '1' # Авто-создание всей иерархии
}

# Путь к новой папке проекта внутри Групповой папки
url = "http://localhost:8080/remote.php/dav/files/admin/GroupFolder/Category/2024/05/Project_1/"

# Создаем структуру через MKCOL или загрузку первого файла
response = requests.request("MKCOL", url, auth=auth, headers=headers)

if response.status_code in [201, 204]:
    # Обязательно сохраняем числовой File ID для Odoo
    file_id = response.headers.get('OC-FileId') # Формат: 00000063instanceid
    # Очищаем ID от ведущих нулей и ID инстанса для сохранения в БД
    numeric_id = int(file_id.split('oc')[0])
```

#### Резюме для администрирования:
*   **Для создания папок и назначения групп:** Используйте OCS API.
*   **Для наполнения и защиты структуры:** Используйте WebDAV с заголовком `AutoMkcol` и расширенные ACL для групповых папок.
*   **Для связи баз данных:** Используйте неизменяемый `oc:fileid` и метод `SEARCH`.