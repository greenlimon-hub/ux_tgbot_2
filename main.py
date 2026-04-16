import asyncio
import sys
from pathlib import Path

# Добавляем папку app в путь поиска модулей
sys.path.insert(0, str(Path(__file__).parent / "app"))

# Теперь импортируем из папки app
from main import main

if __name__ == "__main__":
    asyncio.run(main())
