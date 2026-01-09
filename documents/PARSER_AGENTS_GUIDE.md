# Инструкция по настройке агентов парсинга

## Типы агентов

### 1. Universal Regex Parser (Локальный парсер)

**Когда использовать:**
- Простые текстовые документы со стандартной структурой
- Когда нужна максимальная скорость
- Когда важна конфиденциальность (данные не уходят в интернет)
- Для тестирования без затрат

**Настройка:**
```
Имя: Universal Regex Parser
Тип: Universal Regex Parser
API настройки: не требуются
```

**Ограничения:**
- ❌ Не работает с изображениями
- ❌ Требует четкой структуры документа
- ❌ Может ошибаться на нестандартных форматах

---

### 2. OpenAI-Compatible API (Универсальный AI парсер)

**Поддерживаемые сервисы:**
- OpenAI (GPT-4o, GPT-4o-mini)
- Azure OpenAI
- OpenRouter (доступ к Qwen, Claude, Gemini, Llama и др.)
- Другие OpenAI-совместимые API

**Когда использовать:**
- Любые форматы документов (текст, сканы, фото)
- Нестандартные документы
- Когда нужна высокая точность
- Документы с плохим качеством

#### Настройка OpenAI (GPT-4o-mini)

```
Имя: GPT-4o-mini Parser
Тип: OpenAI-Compatible API (Universal)

API Configuration:
├─ API Key: sk-proj-...  (получить на platform.openai.com)
├─ API Endpoint: https://api.openai.com/v1/chat/completions
└─ Model Name: gpt-4o-mini

Generation Parameters:
├─ Temperature: 0.0 (для точности)
└─ Max Tokens: 4000

Rate Limits (информационно):
├─ RPM: 500
├─ TPM: 200,000
└─ RPD: 10,000
```

**Стоимость:** ~$0.001 за документ (GPT-4o-mini)

#### Настройка Azure OpenAI

```
Имя: Azure GPT-4o
Тип: OpenAI-Compatible API (Universal)

API Configuration:
├─ API Key: <your-azure-key>
├─ API Endpoint: https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=2024-02-15-preview
└─ Model Name: gpt-4o

Generation Parameters:
├─ Temperature: 0.0
└─ Max Tokens: 8000
```

**Как получить:**
1. Создать ресурс Azure OpenAI в портале Azure
2. Развернуть модель (deploy model)
3. Скопировать endpoint и ключ из раздела "Keys and Endpoint"

#### Настройка OpenRouter (Qwen, Claude, и др.)

**OpenRouter** - это прокси-сервис, дающий доступ ко всем популярным AI моделям через единый API.

```
Имя: Qwen 2.5 VL 72B (OpenRouter)
Тип: OpenAI-Compatible API (Universal)

API Configuration:
├─ API Key: sk-or-v1-...  (получить на openrouter.ai)
├─ API Endpoint: https://openrouter.ai/api/v1/chat/completions
└─ Model Name: qwen/qwen-2.5-vl-72b-instruct

Generation Parameters:
├─ Temperature: 0.0
└─ Max Tokens: 8000

Rate Limits:
├─ RPM: 20
└─ TPM: 100,000
```

**Доступные модели через OpenRouter:**
- `qwen/qwen-2.5-vl-72b-instruct` - Qwen (vision, дешевый)
- `anthropic/claude-3.5-sonnet` - Claude (точный)
- `google/gemini-2.0-flash-exp:free` - Gemini (бесплатный)
- `meta-llama/llama-3.2-90b-vision-instruct` - Llama Vision
- И многие другие: https://openrouter.ai/models

**Преимущества OpenRouter:**
- ✅ Один API ключ для всех моделей
- ✅ Нет waitlist (сразу доступ)
- ✅ Есть бесплатные модели
- ✅ Прозрачное ценообразование

---

### 3. Groq API (Llama Vision)

**Что это:**
Groq - это высокопроизводительный хостинг для моделей с открытым исходным кодом, включая Llama-3.2-11b-vision-preview.

**Когда использовать:**
- Быстрая обработка документов (Vision модель)
- Надёжный API с хорошей производительностью
- Поддержка изображений и текста
- Хорошее соотношение цена/качество

#### Настройка Groq Llama Vision

```
Имя: Groq Llama 3.2 Vision (11B)
Тип: Groq API (Llama Vision)

API Configuration:
├─ API Key: gsk-...  (получить на console.groq.com)
├─ API Endpoint: https://api.groq.com/openai/v1/chat/completions
└─ Model Name: llama-3.2-11b-vision-preview

Generation Parameters:
├─ Temperature: 0.1 (для точности)
└─ Max Tokens: 4000

Rate Limits (Free Tier):
├─ RPM: 15
├─ TPM: 15,000
└─ RPD: 500
```

**Формат запроса:**
```json
{
  "model": "llama-3.2-11b-vision-preview",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Оцифруй этот документ в JSON..."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,BASE64_КОД_КАРТИНКИ"
          }
        }
      ]
    }
  ],
  "temperature": 0.1,
  "response_format": { "type": "json_object" }
}
```

**Особенности:**
- ✅ OpenAI-compatible API (легко интегрировать)
- ✅ Поддержка `response_format: json_object`
- ✅ Хорошо работает с украинским языком
- ⚠️ Изображения: макс. 4MB, до 2000x2000 px
- ⚠️ Может "глючить" на очень мелком шрифте

**Как получить API ключ:**
1. Зарегистрироваться на https://console.groq.com
2. Перейти в раздел API Keys
3. Создать новый ключ (начинается с `gsk-`)
4. Скопировать и вставить в настройки агента

**Стоимость (Free Tier):**
- Бесплатно до 500 запросов в день
- После исчерпания - нужен платный план

**Пример интеграции в Python:**
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key="gsk_..."
)

response = client.chat.completions.create(
    model="llama-3.2-11b-vision-preview",
    messages=[...],
    temperature=0.1
)
```

---

### 4. Anthropic Claude (В разработке)

**Когда будет доступно:**
- Прямая интеграция с Anthropic API
- Без использования OpenRouter

**Преимущества:**
- Высокая точность на сложных документах
- Большой context window (200K токенов)
- Отличная работа с украинским языком

---

### 4. Google Gemini

**Что это:**
Прямая интеграция с Google Gemini API. Бесплатный доступ с хорошим качеством распознавания.

**Когда использовать:**
- Бесплатная обработка документов (до 1500/день)
- Хорошая работа с изображениями и текстом
- Быстрая обработка (2-15 секунд)
- Отличное качество для украинских документов

#### Настройка Google Gemini

```
Имя: Google Gemini 2.0 Flash
Тип: Google Gemini

API Configuration:
├─ API Key: AIzaSy...  (получить на aistudio.google.com/app/apikey)
└─ Model Name: gemini-2.0-flash-exp

Generation Parameters:
├─ Temperature: 0.1 (для точности)
└─ Max Tokens: 8192

Rate Limits (Free Tier):
├─ RPM: 15
├─ TPM: 1,000,000
└─ RPD: 1500
```

**Доступные модели:**
- `gemini-2.0-flash-exp` - Экспериментальная, самая быстрая (рекомендуется)
- `gemini-1.5-flash-latest` - Стабильная версия
- `gemini-1.5-pro-latest` - Более мощная (медленнее)

**ВАЖНО:** 
- В настройках указывайте только имя модели БЕЗ префикса `models/`
- Префикс добавляется автоматически кодом
- Пример правильно: `gemini-2.0-flash-exp`
- Пример НЕправильно: `models/gemini-2.0-flash-exp`

**Особенности:**
- ✅ Бесплатно до 1500 запросов/день
- ✅ Multimodal (текст + изображения)
- ✅ JSON response mode
- ✅ Оптимизированные таймауты (20-90с)
- ⚠️ 15 запросов в минуту
- ⚠️ Может зависать при плохом интернете → настройте fallback агента

**Стоимость:** Бесплатно (Free Tier)

**Подробнее:** См. [GOOGLE_GEMINI_SETUP.md](documents/services/GOOGLE_GEMINI_SETUP.md)

---

## Автоматический Fallback (резервный агент)

**Что это:**
Если основной агент не смог обработать документ (ошибка API, таймаут, плохое качество), система автоматически передаст документ резервному агенту.

**Как настроить:**

### Пример 1: Regex → OpenAI
```
Основной агент:
├─ Тип: Universal Regex Parser
└─ Fallback Agent: GPT-4o-mini Parser

Резервный агент:
├─ Тип: OpenAI-Compatible API
└─ Fallback Agent: нет
```

**Логика работы:**
1. Пытаемся разобрать через Regex (быстро, бесплатно)
2. Если не получилось → автоматически отправляем в GPT-4o-mini
3. Результат от GPT возвращаем пользователю

**Когда полезно:**
- Экономия средств (95% документов через regex, 5% через AI)
- Простые документы обрабатываются мгновенно
- Сложные не блокируются

### Пример 2: GPT-4o-mini → GPT-4o
```
Основной агент:
├─ Тип: OpenAI-Compatible API
├─ Model: gpt-4o-mini
└─ Fallback Agent: GPT-4o Full

Резервный агент:
├─ Тип: OpenAI-Compatible API
├─ Model: gpt-4o
└─ Fallback Agent: нет
```

**Логика работы:**
1. Пытаемся через дешевую модель gpt-4o-mini
2. Если ошибка/плохой результат → используем более мощную gpt-4o
3. Баланс между ценой и качеством

### Пример 3: Qwen → Claude
```
Основной агент:
├─ Тип: OpenAI-Compatible API
├─ Endpoint: OpenRouter
├─ Model: qwen/qwen-2.5-vl-72b-instruct
└─ Fallback Agent: Claude via OpenRouter

Резервный агент:
├─ Тип: OpenAI-Compatible API
├─ Endpoint: OpenRouter
├─ Model: anthropic/claude-3.5-sonnet
└─ Fallback Agent: нет
```

**⚠️ Важно:**
- Fallback НЕ создает цикл (если агент A → B, то B не может → A)
- Fallback срабатывает только при ошибке, не при плохом качестве
- Статистика учитывается для обоих агентов

---

## Рекомендуемые конфигурации

### Для экономии средств (Бюджетный вариант)
```
1. Universal Regex Parser (основной)
   └─ Fallback: GPT-4o-mini (OpenAI)

2. GPT-4o-mini (резервный)
   └─ Fallback: нет
```
**Стоимость:** ~$0.10 за 100 документов

### Для максимальной точности (Премиум)
```
1. GPT-4o-mini (основной)
   └─ Fallback: Claude 3.5 Sonnet (OpenRouter)

2. Claude 3.5 Sonnet (резервный)
   └─ Fallback: нет
```
**Стоимость:** ~$1.00 за 100 документов

### Для тестирования (Бесплатно)
```
1. Universal Regex Parser (основной)
   └─ Fallback: Gemini 2.0 Flash (OpenRouter, бесплатный)

2. Gemini 2.0 Flash (резервный)
   └─ Fallback: нет
```
**Стоимость:** $0

---

## Мониторинг и статистика

После настройки агентов следите за статистикой на форме:

- **Usage Count** - сколько раз использовался
- **Total Tokens Used** - всего токенов израсходовано
- **Total Cost** - общая стоимость в USD
- **Last Used** - когда последний раз использовался

**Если агент не используется:**
- Проверьте, выбран ли он в документах
- Проверьте API ключ и endpoint
- Проверьте лимиты (RPM/TPM)

**Если большой расход:**
- Настройте fallback на более дешевую модель
- Используйте regex для простых документов
- Уменьшите max_tokens

---

## Часто задаваемые вопросы

**Q: Можно ли использовать несколько API ключей для одной модели?**
A: Да, создайте несколько агентов с разными ключами и используйте их по очереди.

**Q: Как узнать, сработал ли fallback?**
A: В результате парсинга будет поле `fallback_used: true` и информация о том, какой агент использовался.

**Q: Можно ли создать цепочку из 3+ агентов?**
A: Да, A → B → C → D и т.д. Но будьте осторожны с задержками.

**Q: Что делать, если все агенты не смогли распознать?**
A: Система вернет ошибку со списком попыток. Проверьте качество документа или добавьте более мощную модель в fallback.

**Q: Regex парсер поддерживает изображения?**
A: Нет, только чистый текст. Для изображений используйте AI агенты с vision (GPT-4o, Qwen, Claude, Gemini).

**Q: Можно ли добавить свою AI модель?**
A: Да, если она совместима с OpenAI API (формат запросов/ответов). Укажите свой endpoint в настройках.
