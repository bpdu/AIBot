import requests
import time
import json
import os


from typing import Dict, List
from pathlib import Path

class OpenRouterTester:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.api_key = self._load_api_key()
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost:3000",  # Обязательно для бесплатного использования
            "X-Title": "AI Models Comparison"
        }
    
    def _load_api_key(self) -> str:
        """Загрузка API ключа из конфигурационного файла"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            print(f"Конфигурационный файл '{self.config_file}' не найден.")
            print("Пожалуйста, создайте файл config.json с содержимым:")
            print('''
{
    "openrouter_api_key": "sk-or-v1-ваш_ключ_здесь"
}
''')
            print("\nИли установите переменную окружения:")
            print("export OPENROUTER_API_KEY='sk-or-v1-ваш_ключ_здесь'")
            
            # Проверяем переменные окружения
            env_key = os.getenv("OPENROUTER_API_KEY")
            if env_key:
                print(f"Найден ключ в переменной окружения OPENROUTER_API_KEY")
                return env_key
            
            raise ValueError("API ключ не найден")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get("openrouter_api_key")
                
                if not api_key:
                    raise ValueError("Ключ 'openrouter_api_key' не найден в конфигурационном файле")
                
                # Проверяем формат ключа
                if not api_key.startswith("sk-or-"):
                    print("⚠️ Внимание: API ключ должен начинаться с 'sk-or-'")
                
                return api_key
        except json.JSONDecodeError:
            raise ValueError(f"Ошибка чтения файла {self.config_file}")
    
    def test_connection(self) -> bool:
        """Проверка соединения с OpenRouter"""
        test_payload = {
            "model": "meta-llama/llama-3.2-3b-instruct",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✓ Соединение с OpenRouter успешно установлено")
                return True
            else:
                print(f"✗ Ошибка соединения: HTTP {response.status_code}")
                print(f"Ответ: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Ошибка соединения: {e}")
            return False
    
    def query_model(self, model: str, prompt: str, system_prompt: str = None, max_tokens: int = 500) -> Dict:
        """Отправка запроса к модели"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            start_time = time.perf_counter()
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,  # Используем json вместо data=json.dumps()
                timeout=30
            )
            end_time = time.perf_counter()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                # Получаем точное количество токенов из ответа
                usage = result.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                return {
                    "success": True,
                    "response": result["choices"][0]["message"]["content"],
                    "response_time": response_time,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost": 0,
                    "model": model,
                    "prompt": prompt
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = f"HTTP {response.status_code}: {error_data.get('error', {}).get('message', str(error_data))}"
                except:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                
                return {
                    "success": False,
                    "error": error_msg,
                    "response_time": response_time,
                    "model": model
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Таймаут запроса (30 секунд)",
                "response_time": 30,
                "model": model
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка: {str(e)}",
                "response_time": 0,
                "model": model
            }


def get_free_models() -> List[str]:
    """Возвращает список проверенных бесплатных моделей"""
    return [
        # Меньшие модели (начало списка)
        "meta-llama/llama-3.2-1b-instruct",
        "microsoft/phi-3-mini-128k-instruct",
        "qwen/qwen2.5-0.5b-instruct",
        
        # Средние модели (середина списка)
        "google/gemma-2-2b-it",
        "mistralai/mistral-7b-instruct-v0.3",
        "meta-llama/llama-3.2-3b-instruct",
        
        # Крупные модели (конец списка)
        "google/gemma-2-9b-it",
        "mistralai/mistral-small-3.1-24b-instruct",
        "nousresearch/hermes-3-llama-3.1-405b"  # Эта модель может быть платной, проверьте
    ]


def main():
    """Основная функция"""
    print("="*80)
    print("СРАВНЕНИЕ AI МОДЕЛЕЙ НА OPENROUTER")
    print("="*80)
    
    # Инициализация тестера
    try:
        tester = OpenRouterTester("config.json")
    except ValueError as e:
        print(f"Ошибка: {e}")
        print("\nСоздайте файл config.json с вашим API ключом от OpenRouter")
        print("Получить ключ можно здесь: https://openrouter.ai/keys")
        return
    
    # Проверка соединения
    print("\nПроверка соединения с OpenRouter...")
    if not tester.test_connection():
        print("\n⚠️ Не удалось подключиться к OpenRouter.")
        print("Возможные причины:")
        print("1. Неверный API ключ")
        print("2. Ключ не активирован")
        print("3. Проблемы с интернет-соединением")
        print("\nУбедитесь, что ваш ключ начинается с 'sk-or-v1-'")
        return
    
    # Выбор моделей
    all_models = get_free_models()
    
    # Выбираем 3 модели: начало, середина, конец списка
    models_to_test = [
        all_models[0],  # Начало
        all_models[len(all_models)//2],  # Середина
        all_models[-1]  # Конец
    ]
    
    # Тестовые промпты
    prompts = [
        {
            "name": "Простая математика",
            "prompt": "Сколько будет 2 + 2 * 2?",
            "max_tokens": 100
        },
        {
            "name": "Логическая задача",
            "prompt": "Что тяжелее: килограмм пуха или килограмм железа?",
            "max_tokens": 150
        },
        {
            "name": "Объяснение концепции",
            "prompt": "Объясни, что такое API, простыми словами",
            "max_tokens": 200
        }
    ]
    
    print(f"\nБудут протестированы {len(models_to_test)} модели:")
    for i, model in enumerate(models_to_test, 1):
        print(f"  {i}. {model}")
    
    print(f"\nКоличество промптов: {len(prompts)}")
    print("\nНачинаю тестирование...\n")
    
    # Тестируем модели
    results = {}
    
    for model_idx, model in enumerate(models_to_test, 1):
        print(f"{'='*60}")
        print(f"МОДЕЛЬ {model_idx}: {model}")
        print(f"{'='*60}")
        
        model_results = []
        
        for prompt_idx, prompt_data in enumerate(prompts, 1):
            print(f"\n[{prompt_idx}/{len(prompts)}] {prompt_data['name']}")
            print(f"Вопрос: {prompt_data['prompt']}")
            
            result = tester.query_model(
                model=model,
                prompt=prompt_data["prompt"],
                max_tokens=prompt_data["max_tokens"]
            )
            
            if result["success"]:
                print(f"✓ Время: {result['response_time']:.2f} сек")
                print(f"✓ Токены: {result['total_tokens']}")
                print(f"✓ Ответ: {result['response'][:100]}...")
                model_results.append(result)
            else:
                print(f"✗ Ошибка: {result['error']}")
                model_results.append(result)
            
            # Пауза между запросами
            if prompt_idx < len(prompts):
                time.sleep(1)
        
        results[model] = model_results
        
        # Пауза между моделями
        if model_idx < len(models_to_test):
            time.sleep(2)
    
    # Вывод результатов
    print(f"\n{'='*80}")
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print(f"{'='*80}")
    
    for prompt_idx, prompt_data in enumerate(prompts):
        print(f"\n{'='*60}")
        print(f"ПРОМПТ: {prompt_data['name']}")
        print(f"ВОПРОС: {prompt_data['prompt']}")
        print(f"{'='*60}")
        
        for model in models_to_test:
            if model in results and prompt_idx < len(results[model]):
                result = results[model][prompt_idx]
                model_name = model.split('/')[-1]
                
                print(f"\n--- {model_name} ---")
                
                if result["success"]:
                    print(f"Время: {result['response_time']:.2f} сек")
                    print(f"Токены: {result['total_tokens']} (вход: {result['input_tokens']}, выход: {result['output_tokens']})")
                    print(f"Ответ: {result['response']}\n")
                else:
                    print(f"ОШИБКА: {result['error']}")
    
    # Сводная таблица
    print(f"\n{'='*80}")
    print("СВОДНАЯ ТАБЛИЦА")
    print(f"{'='*80}")
    
    print(f"\n{'Модель':<40} {'Время (сек)':<12} {'Токены':<10} {'Статус':<10}")
    print("-"*80)
    
    for model in models_to_test:
        if model in results:
            model_name = model.split('/')[-1][:38]
            total_time = 0
            total_tokens = 0
            success_count = 0
            
            for result in results[model]:
                if result["success"]:
                    total_time += result["response_time"]
                    total_tokens += result["total_tokens"]
                    success_count += 1
            
            avg_time = total_time / success_count if success_count > 0 else 0
            status = f"{success_count}/{len(prompts)}"
            
            print(f"{model_name:<40} {avg_time:<12.2f} {total_tokens:<10} {status:<10}")
    
    # Сохранение результатов
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"results_{timestamp}.json"
    
    save_data = {
        "timestamp": timestamp,
        "models_tested": models_to_test,
        "prompts": prompts,
        "results": results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nРезультаты сохранены в: {output_file}")


if __name__ == "__main__":
    main()