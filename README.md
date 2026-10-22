# ⚡ Пульс (Pulse AI Ops)

> Открытая платформа операционного управления бизнесом на базе ИИ-агентов.  
> Объединяет отдел продаж (Битрикс24), склад и оплаты (1С), интеллектуальный документооборот и корпоративную базу знаний.

[![CI](https://github.com/shvarev/pulse-ai-ops/actions/workflows/ci.yml/badge.svg)](https://github.com/shvarev/pulse-ai-ops/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61dafb.svg)](https://react.dev/)
[![Tailwind v4](https://img.shields.io/badge/tailwind-v4-38bdf8.svg)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

🌐 **Живой стенд:** [https://demo.shvarev-demo.ru](https://demo.shvarev-demo.ru)  
📱 **Telegram Mini App:** скоро доступен

---

## 🎯 Что решает система

«Пульс» устраняет разрыв между CRM, ERP и реальными действиями сотрудников:

1. **Пульс продаж и сигналы РОПа:**
   - 7 автоматических правил контроля (зависшие сделки, брошенные лиды, потерянные клиенты, просевшие менеджеры).
   - Рейтинг и соблюдение суточных норм активности команды (звонки, конверсии, чеки).
   - Аудит звонков моделью с проверкой соответствия регламентам, цитированием фрагментов речи и рекомендациями.

2. **Сквозная сверка CRM $\leftrightarrow$ 1С:**
   - Автоматическое выявление расхождений между «продано в Битрикс24» и «проведено в 1С» (оплаты без отгрузки, расхождения в суммах счетов).

3. **Интеллектуальный документооборот (LangGraph):**
   - Граф обработки первичных документов: `classify` $\to$ `extract` $\to$ `validate (1С/CRM)` $\to$ `human-in-the-loop confirm` $\to$ `create_draft`.
   - Встроенные предохранители: ни одна проводка не создается без явного подтверждения человеком.

4. **База знаний и регламентов (RAG):**
   - Полнотекстовый поиск FTS5 (bm25) с ранжированием по регламентам компании.
   - Ответы со строгими цитатами и ссылками на первоисточник. Честный ответ «не знаю», если информации нет в базе.

5. **ИИ-Копилот и прозрачность «Под капотом»:**
   - Сквозной диалог поверх всех данных компании на базе **Hermes Agent** через протокол **MCP (Model Context Protocol)**.
   - Живая трассировка рассуждений агента, задействованные инструменты, суб-агенты, задержки и стоимость запросов.
   - Резервный локальный цикл обработки при недоступности внешних моделей.

---

## 🏛 Архитектура

Система построена по принципам **Hexagonal Architecture (Ports & Adapters)**:

```
                            ┌────────────────────────┐
                            │    Web SPA & MiniApp   │
                            │ React 19 + Tailwind v4 │
                            └───────────┬────────────┘
                                        │ REST / SSE
                                        ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                             Pulse Core (FastAPI)                           │
│                                                                            │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌────────────────┐  │
│  │     Modules: Sales    │  │     Modules: Docs     │  │   Knowledge    │  │
│  │ (Pulse, Signals, Team)│  │      (LangGraph)      │  │  (FTS5 + RAG)  │  │
│  └───────────┬───────────┘  └───────────┬───────────┘  └───────┬────────┘  │
│              │                          │                      │           │
│              ▼                          ▼                      ▼           │
│   ┌────────────────────┐     ┌────────────────────┐ ┌───────────────────┐  │
│   │      CrmPort       │     │      ErpPort       │ │  MCP / Agents     │  │
│   │ (Bitrix24 Adapter) │     │    (1C Adapter)    │ │ (Hermes / Local)  │  │
│   └──────────┬─────────┘     └──────────┬─────────┘ └───────────┬───────┘  │
└──────────────┼──────────────────────────┼───────────────────────┼──────────┘
               │                          │                       │
               ▼                          ▼                       ▼
      ┌─────────────────┐        ┌─────────────────┐     ┌─────────────────┐
      │  Bitrix24 REST  │        │     1C OData    │     │   OpenRouter    │
      │   (Live / Mock) │        │   (Live / Mock) │     │ (DeepSeek/Gemini│
      └─────────────────┘        └─────────────────┘     └─────────────────┘
```

- **Взаимозаменяемость эмулятора и боевых систем:**
  Переключение `CRM_MODE=emulator` $\to$ `CRM_MODE=live` и `ERP_MODE=emulator` $\to$ `ERP_MODE=live` меняет источник данных без изменения кода модулей.
- **Бюджетный предохранитель:**
  Глобальный лимит затрат на LLM ($1.5 в сутки) с автоматическим резервированием и возвратом кэшированных ответов при исчерпании.

---

## 🚀 Быстрый старт

### Вариант 1: Docker Compose (рекомендуется)

```bash
git clone https://github.com/shvarev/pulse-ai-ops.git
cd pulse-ai-ops
docker compose up
```

- Интерфейс: `http://localhost:5180`
- API документация: `http://localhost:8010/api/docs`

---

### Вариант 2: Локальная разработка

**Требования:** Python 3.12+, Node.js 22+

1. **Клонирование и настройка окружения:**
   ```bash
   git clone https://github.com/shvarev/pulse-ai-ops.git
   cd pulse-ai-ops
   cp .env.example .env
   ```

2. **Запуск бэкенда (FastAPI):**
   ```bash
   cd apps/api
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   uvicorn pulse.main:app --reload --port 8010
   ```

3. **Запуск фронтенда (React + Vite):**
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```
   Фронтенд запустится на `http://localhost:5180` и проксирует `/api` на `http://127.0.0.1:8010`.

---

## 🧪 Тестирование и качество кода

Репозиторий строго контролируется линтерами и тестами в CI:

```bash
# Проверка бэкенда (Ruff, Mypy Strict, Pytest)
cd apps/api
ruff check .
mypy pulse
pytest --cov=pulse

# Проверка фронтенда (ESLint, TypeScript, Vitest)
cd apps/web
npm run lint
npm run typecheck
npm test

# Проверка гигиены (отсутствие приватных идентификаторов)
python tools/check_private_names.py
```

---

## 📄 Лицензия

MIT License. См. [LICENSE](LICENSE) для подробностей.
