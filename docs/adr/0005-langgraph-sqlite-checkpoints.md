# ADR-005: Персистентность потоков документов через LangGraph SQLite Checkpoints

## Статус
Принято (Accepted)

## Контекст
Автоматическая обработка бухгалтерских и юридических документов в корпоративном секторе не может быть полностью автономной без участия человека (Human-in-the-loop). Если модель ошибочно распознает банковские реквизиты или сумму счёта, прямой вызов API 1С создаст некорректную проводку.
Требовалось:
1. Организовать конвейер распознавания с гарантированной точкой останова (breakpoint) перед созданием проводки.
2. Сохранять состояние графа в персистентном хранилище между перезапусками сервера или перерывами в сессии пользователя.
3. Уметь возобновлять выполнение графа с того же места по сигналу из веб-интерфейса или Telegram-бота.

## Решение
Использован **LangGraph** со встроенным механизмом чекпоинтов на базе **SQLite (`SqliteSaver`)**:

1. **Определение графа (`pulse.modules.docs.graph`):**
   ```python
   workflow = StateGraph(DocProcessingState)
   workflow.add_node("classify", classify_node)
   workflow.add_node("extract", extract_node)
   workflow.add_node("validate", validate_against_erp_node)
   workflow.add_node("review", review_node)
   workflow.add_node("draft", create_erp_draft_node)
   ```

2. **Точка прерывания (Interrupt):**
   Граф компилируется с флагом `interrupt_before=["draft"]`:
   ```python
   checkpointer = SqliteSaver(conn)
   app = workflow.compile(checkpointer=checkpointer, interrupt_before=["draft"])
   ```
   После завершения шага `validate` (сверка с ERP/CRM) граф автоматически приостанавливается и сохраняет полное состояние шагов в таблицу `checkpoints` базы данных SQLite.

3. **Идентификация потоков (`thread_id`):**
   Каждый документ имеет уникальный `thread_id = f"doc_thread_{doc_id}"`.

4. **Возобновление графа (Human-in-the-loop):**
   Когда пользователь нажимает «Подтвердить и провести» в веб-интерфейсе (`POST /api/docs/{id}/confirm`) или инлайн-кнопку в Telegram-боте (`confirm_doc:{id}`), вызывается:
   ```python
   app.invoke(None, config={"configurable": {"thread_id": f"doc_thread_{doc_id}"}})
   ```
   Граф считывает сохраненный чекпоинт, переходит к ноде `draft`, проводит документ со статусом `posted` и завершает работу в ноде `END`.

## Последствия
- 100% защита от несанкционированных и ошибочных проводок в учетной системе.
- Надежное сохранение состояния процессов даже при аварийном перезапуске сервера (Uvicorn).
- Наглядная демонстрация паттерна Human-in-the-loop на живом стенде.
