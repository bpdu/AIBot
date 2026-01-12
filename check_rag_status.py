#!/usr/bin/env python3
"""
Проверка статуса RAG системы
Быстрая диагностика перед запуском бота
"""

import sqlite3
import sys
from pathlib import Path
import subprocess


def check_ollama():
    """Проверить доступность Ollama."""
    print("🔍 Проверка Ollama...")
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            if 'nomic-embed-text' in result.stdout:
                print("   ✅ Ollama работает")
                print("   ✅ Модель nomic-embed-text найдена")
                return True
            else:
                print("   ⚠️  Ollama работает, но модель nomic-embed-text не найдена")
                print("   → Запустите: ollama pull nomic-embed-text")
                return False
        else:
            print("   ❌ Ollama недоступна")
            return False
    except FileNotFoundError:
        print("   ❌ Ollama не установлена")
        print("   → Установите: https://ollama.com/download")
        return False
    except subprocess.TimeoutExpired:
        print("   ⚠️  Ollama не отвечает (timeout)")
        return False
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def check_database():
    """Проверить базу данных embeddings."""
    print("\n🔍 Проверка базы данных...")
    db_path = Path(__file__).parent / "rag" / "db.sqlite3"

    if not db_path.exists():
        print("   ❌ База данных не найдена")
        print(f"   → Путь: {db_path}")
        return False

    print(f"   ✅ База данных найдена: {db_path}")
    print(f"   📦 Размер: {db_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Проверить таблицу project_docs
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверить наличие таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='project_docs'
        """)
        if not cursor.fetchone():
            print("   ❌ Таблица project_docs не найдена")
            print("   → Запустите: cd rag && python create-project-docs-embeddings.py")
            conn.close()
            return False

        print("   ✅ Таблица project_docs найдена")

        # Подсчитать количество записей
        cursor.execute("SELECT COUNT(*) FROM project_docs")
        count = cursor.fetchone()[0]

        if count == 0:
            print("   ⚠️  Таблица пуста (0 записей)")
            print("   → Запустите: cd rag && python create-project-docs-embeddings.py")
            conn.close()
            return False

        print(f"   ✅ Записей в таблице: {count}")

        # Проверить документы
        cursor.execute("SELECT DISTINCT doc_name FROM project_docs")
        docs = [row[0] for row in cursor.fetchall()]
        print(f"   📄 Индексированные документы:")
        for doc in docs:
            cursor.execute("SELECT COUNT(*) FROM project_docs WHERE doc_name = ?", (doc,))
            doc_count = cursor.fetchone()[0]
            print(f"      • {doc}: {doc_count} chunks")

        conn.close()
        return True

    except sqlite3.OperationalError as e:
        print(f"   ❌ Ошибка базы данных: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def check_documents():
    """Проверить наличие документов для индексации."""
    print("\n🔍 Проверка документов...")
    project_root = Path(__file__).parent

    docs = [
        "README.md",
        "ARCHITECTURE.md",
        "CODE_STYLE.md",
        "docs/OLLAMA_SETUP.md",
        "docs/EMBEDDINGS_GUIDE.md"
    ]

    all_exist = True
    for doc in docs:
        doc_path = project_root / doc
        if doc_path.exists():
            size_kb = doc_path.stat().st_size / 1024
            print(f"   ✅ {doc} ({size_kb:.1f} KB)")
        else:
            print(f"   ❌ {doc} - не найден")
            all_exist = False

    return all_exist


def main():
    """Главная функция."""
    print("=" * 60)
    print("RAG System Status Check")
    print("=" * 60)

    # Проверки
    ollama_ok = check_ollama()
    db_ok = check_database()
    docs_ok = check_documents()

    # Итоги
    print("\n" + "=" * 60)
    print("📊 Итоги проверки:")
    print("=" * 60)

    if ollama_ok and db_ok and docs_ok:
        print("✅ Все компоненты работают!")
        print("\n🚀 Можно запускать бота:")
        print("   python bot.py")
        print("\n💡 И пробовать команду /help:")
        print("   /help как установить ollama")
        return 0
    else:
        print("⚠️  Есть проблемы:\n")

        if not ollama_ok:
            print("❌ Ollama:")
            print("   1. Установите Ollama: https://ollama.com/download")
            print("   2. Загрузите модель: ollama pull nomic-embed-text")

        if not db_ok:
            print("❌ База данных:")
            print("   Создайте embeddings:")
            print("   cd rag && python create-project-docs-embeddings.py")

        if not docs_ok:
            print("❌ Документы:")
            print("   Некоторые документы отсутствуют")
            print("   Проверьте структуру проекта")

        print("\n📖 Подробнее: docs/QUICK_FIX.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
