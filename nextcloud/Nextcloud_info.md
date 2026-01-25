# **Справочник работы с Nextcloud**

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
match = re.match(r'^(\\d+)', raw_id)
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
          <d:and>
            <d:eq>
              <d:prop><oc:fileid/></d:prop>
              <d:literal>{file_id}</d:literal>
            </d:eq>
            <d:is-collection/>
          </d:and>
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

Если потребуется дополнить справочник или внести изменения, дайте знать!