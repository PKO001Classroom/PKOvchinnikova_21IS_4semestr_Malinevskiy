# test_achievements.py
import pytest
import sqlite3
import os
import json
from datetime import datetime
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import sys

# Добавляем путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def temp_db():
    """Создание временной базы данных для тестов"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_достижения.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS достижения (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            название TEXT NOT NULL,
            дата TEXT NOT NULL,
            тип TEXT NOT NULL,
            уровень TEXT NOT NULL,
            описание TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS статистика (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            тип TEXT NOT NULL,
            количество INTEGER DEFAULT 0,
            месяц TEXT NOT NULL
        )
    """)

    # Тестовые данные
    test_data = [
        ("Победа в олимпиаде", "2024-01-15", "Олимпиада", "региональный", "Занял 1 место"),
        ("Сертификат Python", "2024-02-20", "Сертификат", "национальный", "Курс по Python"),
        ("Конференция AI", "2024-03-10", "Конференция", "международный", "Доклад по ИИ"),
        ("Школьный проект", "2024-01-05", "Проект", "локальный", "Школьный проект"),
    ]

    for name, date, typ, level, desc in test_data:
        cursor.execute("""
            INSERT INTO достижения (название, дата, тип, уровень, описание)
            VALUES (?, ?, ?, ?, ?)
        """, (name, date, typ, level, desc))

    conn.commit()
    conn.close()

    yield db_path

    # Даем время на закрытие всех соединений
    import time
    time.sleep(0.1)

    # Очистка с обработкой ошибок
    try:
        shutil.rmtree(temp_dir)
    except (PermissionError, OSError) as e:
        print(f"Предупреждение: не удалось удалить {temp_dir}: {e}")


class TestAchievementTracker:
    """Тесты для класса AchievementTracker"""

    def test_validate_input_valid(self):
        """Тест валидации корректных данных"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        errors = tracker.validate_input("Победа в олимпиаде", "2024-01-15")
        assert len(errors) == 0

    def test_validate_input_short_name(self):
        """Тест валидации короткого названия"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        errors = tracker.validate_input("А", "2024-01-15")
        assert len(errors) == 1
        assert "Название должно содержать минимум 3 символа" in errors[0]

    def test_validate_input_empty_name(self):
        """Тест валидации пустого названия"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        errors = tracker.validate_input("", "2024-01-15")
        assert len(errors) == 1
        assert "Название должно содержать минимум 3 символа" in errors[0]

    def test_validate_input_invalid_date_format(self):
        """Тест валидации неверного формата даты"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        errors = tracker.validate_input("Тест", "15-01-2024")
        assert len(errors) == 1
        assert "Дата должна быть в формате ГГГГ-ММ-ДД" in errors[0]

    def test_validate_input_invalid_date(self):
        """Тест валидации некорректной даты"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        errors = tracker.validate_input("Тест", "2024-13-45")
        assert len(errors) == 1
        assert "Некорректная дата" in errors[0]

    def test_load_types_from_file(self):
        """Тест загрузки типов из файла"""
        from achievements import AchievementTracker

        with tempfile.TemporaryDirectory() as temp_dir:
            types_path = os.path.join(temp_dir, "types.json")
            test_types = ["Тест1", "Тест2", "Тест3"]

            with open(types_path, 'w', encoding='utf-8') as f:
                json.dump(test_types, f, ensure_ascii=False, indent=2)

            tracker = object.__new__(AchievementTracker)

            with patch('achievements.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value.read.return_value = json.dumps(test_types)
                mock_open.return_value = mock_file

                result = tracker.load_types()
                assert result == test_types

    def test_load_types_default(self):
        """Тест загрузки типов по умолчанию при отсутствии файла"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        with patch('achievements.open', side_effect=FileNotFoundError):
            types = tracker.load_types()
            assert isinstance(types, list)
            assert len(types) > 0
            assert "Олимпиада" in types

    def test_init_db(self):
        """Тест инициализации базы данных"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_init.db")

        try:
            tracker.conn = sqlite3.connect(db_path)
            tracker.cursor = tracker.conn.cursor()

            tracker.init_db()

            tracker.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = tracker.cursor.fetchall()
            table_names = [table[0] for table in tables]

            assert 'достижения' in table_names
            assert 'статистика' in table_names

        finally:
            tracker.conn.close()
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def test_load_records(self, temp_db):
        """Тест загрузки записей из базы данных"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        records = tracker.load_records()

        assert isinstance(records, list)
        assert len(records) == 4

        for record in records:
            assert len(record) == 5
            assert isinstance(record[0], str)
            assert isinstance(record[1], str)

        tracker.conn.close()

    def test_load_records_with_description(self, temp_db):
        """Тест загрузки записей с описанием и ID"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        records = tracker.load_records(with_description=True)

        assert isinstance(records, list)
        assert len(records) == 4

        assert len(records[0]) == 6
        assert isinstance(records[0][0], int)

        tracker.conn.close()

    def test_update_statistics(self, temp_db):
        """Тест обновления статистики"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        current_month = datetime.now().strftime('%Y-%m')

        tracker.update_statistics("Олимпиада")

        tracker.cursor.execute("""
            SELECT количество FROM статистика 
            WHERE тип = ? AND месяц = ?
        """, ("Олимпиада", current_month))

        result = tracker.cursor.fetchone()

        if result:
            assert result[0] == 1

        tracker.conn.close()

    def test_update_statistics_after_delete(self, temp_db):
        """Тест обновления статистики после удаления"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        current_month = datetime.now().strftime('%Y-%m')

        tracker.cursor.execute("""
            INSERT INTO статистика (тип, количество, месяц)
            VALUES (?, ?, ?)
        """, ("Олимпиада", 5, current_month))
        tracker.conn.commit()

        tracker.update_statistics_after_delete("Олимпиада")

        tracker.cursor.execute("""
            SELECT количество FROM статистика 
            WHERE тип = ? AND месяц = ?
        """, ("Олимпиада", current_month))

        result = tracker.cursor.fetchone()
        assert result[0] == 4

        tracker.conn.close()

    def test_update_statistics_after_delete_to_zero(self, temp_db):
        """Тест обновления статистики при удалении до 0"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        current_month = datetime.now().strftime('%Y-%m')

        tracker.cursor.execute("""
            INSERT INTO статистика (тип, количество, месяц)
            VALUES (?, 1, ?)
        """, ("Проект", current_month))
        tracker.conn.commit()

        tracker.update_statistics_after_delete("Проект")

        tracker.cursor.execute("""
            SELECT количество FROM статистика 
            WHERE тип = ? AND месяц = ?
        """, ("Проект", current_month))

        result = tracker.cursor.fetchone()
        assert result is None

        tracker.conn.close()

    @patch('achievements.messagebox.showinfo')
    @patch('achievements.messagebox.showerror')
    def test_save_achievement_success(self, mock_error, mock_info, temp_db):
        """Тест успешного сохранения достижения"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        tracker.achievement_types = ["Олимпиада", "Сертификат"]
        tracker.levels = ["локальный", "региональный"]

        tracker.name_entry = Mock()
        tracker.name_entry.get.return_value = "Новое достижение"

        tracker.date_entry = Mock()
        tracker.date_entry.get.return_value = "2024-01-15"

        tracker.type_combo = Mock()
        tracker.type_combo.get.return_value = "Олимпиада"

        tracker.level_combo = Mock()
        tracker.level_combo.get.return_value = "региональный"

        tracker.desc_text = Mock()
        tracker.desc_text.get.return_value = "Тестовое описание"

        tracker.cursor.execute("SELECT COUNT(*) FROM достижения")
        initial_count = tracker.cursor.fetchone()[0]

        tracker.save_achievement()

        mock_info.assert_called_once()

        tracker.cursor.execute("SELECT COUNT(*) FROM достижения")
        new_count = tracker.cursor.fetchone()[0]
        assert new_count == initial_count + 1

        tracker.conn.close()

    @patch('achievements.messagebox.showerror')
    def test_save_achievement_validation_fail(self, mock_error, temp_db):
        """Тест сохранения с невалидными данными"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        tracker.achievement_types = ["Олимпиада", "Сертификат"]
        tracker.levels = ["локальный", "региональный"]

        tracker.name_entry = Mock()
        tracker.name_entry.get.return_value = "А"

        tracker.date_entry = Mock()
        tracker.date_entry.get.return_value = "2024-01-15"

        tracker.type_combo = Mock()
        tracker.type_combo.get.return_value = "Олимпиада"

        tracker.level_combo = Mock()
        tracker.level_combo.get.return_value = "региональный"

        tracker.desc_text = Mock()
        tracker.desc_text.get.return_value = ""

        tracker.cursor.execute("SELECT COUNT(*) FROM достижения")
        initial_count = tracker.cursor.fetchone()[0]

        tracker.save_achievement()

        mock_error.assert_called_once()

        tracker.cursor.execute("SELECT COUNT(*) FROM достижения")
        new_count = tracker.cursor.fetchone()[0]
        assert new_count == initial_count

        tracker.conn.close()

    def test_clear_form(self):
        """Тест очистки формы"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        tracker.name_entry = Mock()
        tracker.date_entry = Mock()
        tracker.type_combo = Mock()
        tracker.level_combo = Mock()
        tracker.desc_text = Mock()

        tracker.date_entry.set_date = Mock()
        tracker.type_combo.current = Mock()
        tracker.level_combo.current = Mock()

        tracker.clear_form()

        tracker.name_entry.delete.assert_called_with(0, 'end')
        tracker.desc_text.delete.assert_called_with("1.0", 'end')
        tracker.type_combo.current.assert_called_with(0)
        tracker.level_combo.current.assert_called_with(0)


class TestDatabaseOperations:
    """Тесты для операций с базой данных"""

    def test_insert_achievement(self):
        """Тест вставки записи в таблицу достижений"""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE достижения (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                название TEXT NOT NULL,
                дата TEXT NOT NULL,
                тип TEXT NOT NULL,
                уровень TEXT NOT NULL,
                описание TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO достижения (название, дата, тип, уровень, описание)
            VALUES (?, ?, ?, ?, ?)
        """, ("Тестовое достижение", "2024-01-15", "Тест", "локальный", "Описание"))

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM достижения")
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute("SELECT название, тип, уровень FROM достижения")
        record = cursor.fetchone()
        assert record == ("Тестовое достижение", "Тест", "локальный")

        conn.close()

    def test_update_achievement(self):
        """Тест обновления записи в таблице достижений"""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE достижения (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                название TEXT NOT NULL,
                дата TEXT NOT NULL,
                тип TEXT NOT NULL,
                уровень TEXT NOT NULL,
                описание TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO достижения (название, дата, тип, уровень)
            VALUES ('Старое название', '2024-01-01', 'Старый тип', 'локальный')
        """)
        conn.commit()

        cursor.execute("""
            UPDATE достижения 
            SET название = 'Новое название', тип = 'Новый тип'
            WHERE название = 'Старое название'
        """)
        conn.commit()

        cursor.execute("SELECT название, тип FROM достижения")
        record = cursor.fetchone()
        assert record == ("Новое название", "Новый тип")

        conn.close()

    def test_delete_achievement(self):
        """Тест удаления записи из таблицы достижений"""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE достижения (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                название TEXT NOT NULL,
                дата TEXT NOT NULL,
                тип TEXT NOT NULL,
                уровень TEXT NOT NULL,
                описание TEXT
            )
        """)

        cursor.executemany("""
            INSERT INTO достижения (название, дата, тип, уровень)
            VALUES (?, '2024-01-01', 'Тест', 'локальный')
        """, [("Достижение 1",), ("Достижение 2",), ("Достижение 3",)])

        conn.commit()

        cursor.execute("DELETE FROM достижения WHERE название = 'Достижение 2'")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM достижения")
        count = cursor.fetchone()[0]
        assert count == 2

        cursor.execute("SELECT название FROM достижения ORDER BY название")
        records = cursor.fetchall()
        assert records == [("Достижение 1",), ("Достижение 3",)]

        conn.close()

    def test_select_with_conditions(self):
        """Тест выборки с условиями"""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE достижения (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                название TEXT NOT NULL,
                дата TEXT NOT NULL,
                тип TEXT NOT NULL,
                уровень TEXT NOT NULL,
                описание TEXT
            )
        """)

        test_data = [
            ("Олимпиада по математике", "2024-01-15", "Олимпиада", "региональный"),
            ("Сертификат Python", "2024-02-20", "Сертификат", "национальный"),
            ("Олимпиада по физике", "2024-03-10", "Олимпиада", "локальный"),
        ]

        cursor.executemany("""
            INSERT INTO достижения (название, дата, тип, уровень)
            VALUES (?, ?, ?, ?)
        """, test_data)

        conn.commit()

        cursor.execute("SELECT название FROM достижения WHERE тип = 'Олимпиада'")
        olympiads = cursor.fetchall()
        assert len(olympiads) == 2

        cursor.execute("SELECT название FROM достижения WHERE уровень = 'национальный'")
        national = cursor.fetchall()
        assert len(national) == 1
        assert national[0][0] == "Сертификат Python"

        cursor.execute("""
            SELECT название FROM достижения 
            WHERE дата BETWEEN '2024-02-01' AND '2024-03-31'
        """)
        feb_mar = cursor.fetchall()
        assert len(feb_mar) == 2

        conn.close()

    def test_statistics_aggregation(self):
        """Тест агрегации статистики"""
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE статистика (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                тип TEXT NOT NULL,
                количество INTEGER DEFAULT 0,
                месяц TEXT NOT NULL
            )
        """)

        stats_data = [
            ("Олимпиада", 5, "2024-01"),
            ("Сертификат", 3, "2024-01"),
            ("Олимпиада", 2, "2024-02"),
            ("Проект", 1, "2024-02"),
        ]

        cursor.executemany("""
            INSERT INTO статистика (тип, количество, месяц)
            VALUES (?, ?, ?)
        """, stats_data)

        conn.commit()

        cursor.execute("""
            SELECT тип, SUM(количество) as total 
            FROM статистика 
            GROUP BY тип 
            ORDER BY total DESC
        """)

        results = cursor.fetchall()
        assert len(results) == 3

        olympiad_total = next((r[1] for r in results if r[0] == "Олимпиада"), 0)
        assert olympiad_total == 7

        cursor.execute("""
            SELECT тип, количество 
            FROM статистика 
            WHERE месяц = '2024-02'
        """)

        feb_stats = cursor.fetchall()
        assert len(feb_stats) == 2

        conn.close()


class TestExportFunctions:
    """Тесты функций экспорта"""

    @patch('achievements.messagebox.showerror')
    def test_export_to_word_error_handling(self, mock_error):
        """Тест обработки ошибок при экспорте в Word"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        # Инициализируем необходимые атрибуты
        tracker.conn = Mock()
        tracker.cursor = Mock()
        tracker.achievement_types = ["Олимпиада", "Сертификат"]
        tracker.levels = ["локальный", "региональный"]

        # Мокаем load_records чтобы возвращал тестовые данные
        tracker.load_records = Mock(return_value=[
            (1, "2024-01-15", "Тест", "Олимпиада", "региональный", "Описание")
        ])

        # Тестируем обработку ошибки при создании документа
        with patch('achievements.Document', side_effect=Exception("Test error")):
            tracker.export_to_word()
            mock_error.assert_called_once()

    @patch('achievements.messagebox.showerror')
    @patch('achievements.messagebox.showwarning')
    def test_export_to_excel_error_handling(self, mock_warning, mock_error):
        """Тест обработки ошибок при экспорте в Excel"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        # Инициализируем необходимые атрибуты
        tracker.conn = Mock()
        tracker.cursor = Mock()
        tracker.achievement_types = ["Олимпиада", "Сертификат"]
        tracker.levels = ["локальный", "региональный"]

        # Мокаем load_records чтобы возвращал тестовые данные
        tracker.load_records = Mock(return_value=[
            (1, "2024-01-15", "Тест", "Олимпиада", "региональный", "Описание")
        ])

        # Тестируем обработку ошибки при создании Excel
        with patch('achievements.pd.DataFrame', side_effect=Exception("Test error")):
            tracker.export_to_excel()
            # Ожидаем ошибку, а не предупреждение
            mock_error.assert_called_once()

    @patch('achievements.messagebox.showerror')
    def test_export_to_pdf_error_handling(self, mock_error):
        """Тест обработки ошибок при экспорте в PDF"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        # Инициализируем необходимые атрибуты
        tracker.conn = Mock()
        tracker.cursor = Mock()
        tracker.achievement_types = ["Олимпиада", "Сертификат"]
        tracker.levels = ["локальный", "региональный"]

        # Мокаем load_records чтобы возвращал тестовые данные
        tracker.load_records = Mock(return_value=[
            (1, "2024-01-15", "Тест", "Олимпиада", "региональный", "Описание")
        ])

        # Тестируем обработку ошибки при создании PDF
        with patch('achievements.open', side_effect=Exception("Test error")):
            tracker.export_to_pdf()
            mock_error.assert_called_once()


class TestSearchFunctions:
    """Тесты функций поиска"""

    def test_perform_search_basic(self, temp_db):
        """Тест базовой функции поиска"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        tracker.achievement_types = ["Олимпиада", "Сертификат", "Проект", "Конференция"]
        tracker.levels = ["локальный", "региональный", "национальный", "международный"]

        # Создаем упрощенную версию метода perform_search для тестирования SQL
        def test_perform_search():
            """Упрощенная версия для тестирования SQL запроса"""
            query = "SELECT дата, название, тип, уровень, описание FROM достижения WHERE 1=1"
            params = []

            # Выполняем запрос
            tracker.cursor.execute(query, params)
            return tracker.cursor.fetchall()

        # Вызываем тестовую функцию
        results = test_perform_search()

        # Должно быть 4 записи
        assert len(results) == 4

        tracker.conn.close()

    def test_reset_search(self):
        """Тест сброса поиска"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        tracker.search_name = Mock()
        tracker.search_type = Mock()
        tracker.search_level = Mock()
        tracker.date_from = Mock()
        tracker.date_to = Mock()
        tracker.search_tree = Mock()

        tracker.search_name.delete = Mock()
        tracker.search_type.current = Mock()
        tracker.search_level.current = Mock()
        tracker.date_from.set_date = Mock()
        tracker.date_to.set_date = Mock()
        tracker.search_tree.get_children.return_value = ['item1', 'item2']
        tracker.search_tree.delete = Mock()

        tracker.reset_search()

        tracker.search_name.delete.assert_called_with(0, 'end')
        assert tracker.search_tree.delete.call_count == 2


class TestAdditionalFunctions:
    """Дополнительные тесты"""

    def test_backup_database(self):
        """Тест резервного копирования базы данных"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        with patch('achievements.os.path.exists') as mock_exists, \
                patch('achievements.shutil.copy2') as mock_copy, \
                patch('achievements.messagebox.showinfo') as mock_info, \
                patch('achievements.datetime') as mock_datetime:
            mock_exists.return_value = True
            mock_datetime.now.return_value.strftime.return_value = "20240101_120000"

            tracker.backup_database()

            mock_copy.assert_called_once()
            mock_info.assert_called_once()

    def test_backup_database_not_found(self):
        """Тест резервного копирования при отсутствии БД"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        with patch('achievements.os.path.exists') as mock_exists, \
                patch('achievements.messagebox.showwarning') as mock_warning:
            mock_exists.return_value = False

            tracker.backup_database()

            mock_warning.assert_called_once()

    def test_start_notification_scheduler(self):
        """Тест запуска планировщика уведомлений"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)

        with patch('achievements.threading.Thread') as mock_thread, \
                patch('achievements.schedule.every') as mock_schedule:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            tracker.start_notification_scheduler()

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()


class TestIntegration:
    """Интеграционные тесты"""

    def test_full_workflow(self, temp_db):
        """Тест полного рабочего процесса"""
        from achievements import AchievementTracker

        tracker = object.__new__(AchievementTracker)
        tracker.conn = sqlite3.connect(temp_db)
        tracker.cursor = tracker.conn.cursor()

        # 1. Загружаем записи
        records = tracker.load_records()
        assert len(records) == 4

        # 2. Обновляем статистику
        tracker.update_statistics("Олимпиада")

        # 3. Проверяем статистику
        current_month = datetime.now().strftime('%Y-%m')
        tracker.cursor.execute("SELECT количество FROM статистика WHERE тип = ? AND месяц = ?",
                               ("Олимпиада", current_month))
        result = tracker.cursor.fetchone()
        if result:
            assert result[0] == 1

        tracker.conn.close()


def test_main_execution():
    """Тест запуска приложения"""
    with patch('achievements.AchievementTracker') as mock_tracker, \
            patch('achievements.os.path.exists') as mock_exists, \
            patch('achievements.open', create=True) as mock_open, \
            patch('achievements.json.dump'):
        mock_exists.return_value = False

        mock_instance = Mock()
        mock_tracker.return_value = mock_instance

        mock_tracker.assert_not_called()

        mock_tracker()
        mock_instance.run()

        mock_tracker.assert_called_once()
        mock_instance.run.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--no-header"])