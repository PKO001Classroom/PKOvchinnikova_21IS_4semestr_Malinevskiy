"""
Менеджер тем для клиента Local Messenger.
Поддержка светлой и темной темы.
"""

import json
import os
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QFile, QTextStream
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtWidgets import QApplication, QStyleFactory
import logging

logger = logging.getLogger(__name__)


class ThemeManager(QObject):
    """
    Менеджер тем для изменения внешнего вида приложения.
    """
    
    theme_changed = pyqtSignal(str)  # Сигнал при изменении темы
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_theme = "light"
        self.themes = {}
        self.custom_styles = {}
        
        self.load_themes()
        self.load_settings()
        
        logger.info(f"ThemeManager инициализирован. Текущая тема: {self.current_theme}")
    
    def load_themes(self):
        """Загрузка доступных тем"""
        # Базовые темы
        self.themes = {
            "light": {
                "name": "Светлая",
                "type": "builtin",
                "palette": "light",
                "styles": self.get_light_styles()
            },
            "dark": {
                "name": "Темная",
                "type": "builtin",
                "palette": "dark",
                "styles": self.get_dark_styles()
            },
            "blue": {
                "name": "Синяя",
                "type": "builtin",
                "palette": "light",
                "styles": self.get_blue_styles()
            },
            "midnight": {
                "name": "Полуночная",
                "type": "builtin",
                "palette": "dark",
                "styles": self.get_midnight_styles()
            }
        }
        
        # Загружаем пользовательские темы
        self.load_custom_themes()
        
        logger.debug(f"Загружено тем: {len(self.themes)}")
    
    def load_custom_themes(self):
        """Загрузка пользовательских тем из файлов"""
        try:
            themes_dir = self.get_themes_directory()
            
            if not themes_dir.exists():
                themes_dir.mkdir(parents=True, exist_ok=True)
                self.create_default_theme_files(themes_dir)
                return
            
            # Ищем JSON файлы с темами
            for theme_file in themes_dir.glob("*.json"):
                try:
                    with open(theme_file, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)
                    
                    theme_name = theme_data.get("name", theme_file.stem)
                    self.themes[theme_name] = {
                        "name": theme_name,
                        "type": "custom",
                        "file": str(theme_file),
                        "data": theme_data
                    }
                    
                    logger.debug(f"Загружена пользовательская тема: {theme_name}")
                    
                except Exception as e:
                    logger.error(f"Ошибка загрузки темы {theme_file}: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка загрузки пользовательских тем: {e}")
    
    def create_default_theme_files(self, themes_dir):
        """Создание файлов тем по умолчанию"""
        default_themes = {
            "green": {
                "name": "Зеленая",
                "palette": "light",
                "colors": {
                    "primary": "#4CAF50",
                    "secondary": "#81C784",
                    "accent": "#388E3C",
                    "background": "#F1F8E9",
                    "surface": "#FFFFFF",
                    "text_primary": "#212121",
                    "text_secondary": "#757575",
                    "border": "#C8E6C9"
                }
            },
            "purple": {
                "name": "Фиолетовая",
                "palette": "dark",
                "colors": {
                    "primary": "#9C27B0",
                    "secondary": "#BA68C8",
                    "accent": "#7B1FA2",
                    "background": "#121212",
                    "surface": "#1E1E1E",
                    "text_primary": "#E1E1E1",
                    "text_secondary": "#AAAAAA",
                    "border": "#2D2D2D"
                }
            }
        }
        
        for theme_name, theme_data in default_themes.items():
            theme_file = themes_dir / f"{theme_name}.json"
            try:
                with open(theme_file, 'w', encoding='utf-8') as f:
                    json.dump(theme_data, f, indent=2, ensure_ascii=False)
                logger.debug(f"Создана тема по умолчанию: {theme_name}")
            except Exception as e:
                logger.error(f"Ошибка создания темы {theme_name}: {e}")
    
    def get_themes_directory(self):
        """Получение директории тем"""
        from config import APP_DATA_DIR
        return Path(APP_DATA_DIR) / "themes"
    
    def load_settings(self):
        """Загрузка настроек темы"""
        try:
            from client.auth_manager import get_auth_manager
            auth_manager = get_auth_manager()
            
            self.current_theme = auth_manager.get_setting('theme', 'light')
            
            # Проверяем, что тема существует
            if self.current_theme not in self.themes:
                self.current_theme = "light"
            
            logger.debug(f"Текущая тема: {self.current_theme}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек темы: {e}")
    
    def save_settings(self):
        """Сохранение настроек темы"""
        try:
            from client.auth_manager import get_auth_manager
            auth_manager = get_auth_manager()
            
            auth_manager.set_setting('theme', self.current_theme)
            
            logger.debug("Настройки темы сохранены")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек темы: {e}")
    
    def set_theme(self, theme_name):
        """
        Установка темы.
        
        Args:
            theme_name: Имя темы для установки
        """
        if theme_name not in self.themes:
            logger.error(f"Тема не найдена: {theme_name}")
            return False
        
        try:
            old_theme = self.current_theme
            self.current_theme = theme_name
            
            # Применяем тему
            self.apply_theme()
            
            # Сохраняем настройки
            self.save_settings()
            
            # Отправляем сигнал
            self.theme_changed.emit(theme_name)
            
            logger.info(f"Тема изменена: {old_theme} -> {theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка установки темы {theme_name}: {e}")
            return False
    
    def apply_theme(self):
        """Применение текущей темы к приложению"""
        try:
            app = QApplication.instance()
            if not app:
                logger.error("QApplication не инициализирован")
                return
            
            theme_data = self.themes[self.current_theme]
            
            # Применяем палитру
            if theme_data.get("palette") == "dark":
                self.apply_dark_palette(app)
            else:
                self.apply_light_palette(app)
            
            # Применяем стили
            styles = theme_data.get("styles", {})
            self.apply_styles(app, styles)
            
            # Для пользовательских тем применяем дополнительные стили
            if theme_data.get("type") == "custom":
                self.apply_custom_theme(theme_data)
            
            logger.debug(f"Тема '{self.current_theme}' применена")
            
        except Exception as e:
            logger.error(f"Ошибка применения темы: {e}")
    
    def apply_dark_palette(self, app):
        """Применение темной палитры"""
        dark_palette = QPalette()
        
        # Цвета для темной темы
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
        
        app.setPalette(dark_palette)
    
    def apply_light_palette(self, app):
        """Применение светлой палитры"""
        app.setPalette(app.style().standardPalette())
    
    def apply_styles(self, app, styles):
        """Применение стилей"""
        if not styles:
            return
        
        style_sheet = self.generate_stylesheet(styles)
        app.setStyleSheet(style_sheet)
    
    def generate_stylesheet(self, styles):
        """Генерация CSS стилей из словаря"""
        css = ""
        
        for selector, properties in styles.items():
            css += f"{selector} {{\n"
            for prop, value in properties.items():
                css += f"    {prop}: {value};\n"
            css += "}\n\n"
        
        return css
    
    def apply_custom_theme(self, theme_data):
        """Применение пользовательской темы"""
        try:
            custom_data = theme_data.get("data", {})
            colors = custom_data.get("colors", {})
            
            if not colors:
                return
            
            # Создаем CSS стили из цветов темы
            styles = self.generate_custom_styles(colors)
            
            # Применяем стили
            app = QApplication.instance()
            if app:
                app.setStyleSheet(styles)
                
        except Exception as e:
            logger.error(f"Ошибка применения пользовательской темы: {e}")
    
    def generate_custom_styles(self, colors):
        """Генерация стилей из пользовательских цветов"""
        primary = colors.get("primary", "#1976d2")
        secondary = colors.get("secondary", "#2196F3")
        accent = colors.get("accent", "#FF4081")
        background = colors.get("background", "#FFFFFF")
        surface = colors.get("surface", "#F5F5F5")
        text_primary = colors.get("text_primary", "#212121")
        text_secondary = colors.get("text_secondary", "#757575")
        border = colors.get("border", "#E0E0E0")
        
        styles = f"""
        /* Основные стили */
        QWidget {{
            background-color: {background};
            color: {text_primary};
            font-family: 'Segoe UI', 'Arial', sans-serif;
        }}
        
        QPushButton {{
            background-color: {primary};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        QPushButton:hover {{
            background-color: {secondary};
        }}
        
        QPushButton:pressed {{
            background-color: {accent};
        }}
        
        QLineEdit, QTextEdit {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 8px;
        }}
        
        QLineEdit:focus, QTextEdit:focus {{
            border: 2px solid {primary};
        }}
        
        QListWidget {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: 4px;
        }}
        
        QListWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {border};
        }}
        
        QListWidget::item:selected {{
            background-color: {primary};
            color: white;
        }}
        
        QTabWidget::pane {{
            border: 1px solid {border};
            background-color: {background};
        }}
        
        QTabBar::tab {{
            background-color: {surface};
            color: {text_secondary};
            padding: 8px 16px;
            border: 1px solid {border};
            border-bottom: none;
        }}
        
        QTabBar::tab:selected {{
            background-color: {background};
            color: {text_primary};
            font-weight: bold;
            border-bottom: 2px solid {primary};
        }}
        
        QGroupBox {{
            border: 2px solid {border};
            border-radius: 6px;
            margin-top: 10px;
            font-weight: bold;
            color: {text_primary};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}
        
        QScrollBar:vertical {{
            background-color: {surface};
            width: 12px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {border};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {text_secondary};
        }}
        """
        
        return styles
    
    def get_available_themes(self):
        """Получение списка доступных тем"""
        themes_list = []
        
        for theme_id, theme_data in self.themes.items():
            themes_list.append({
                'id': theme_id,
                'name': theme_data.get('name', theme_id),
                'type': theme_data.get('type', 'builtin'),
                'current': (theme_id == self.current_theme)
            })
        
        return sorted(themes_list, key=lambda x: (x['type'] != 'builtin', x['name']))
    
    def get_current_theme_info(self):
        """Получение информации о текущей теме"""
        if self.current_theme not in self.themes:
            return None
        
        theme_data = self.themes[self.current_theme]
        
        return {
            'id': self.current_theme,
            'name': theme_data.get('name', self.current_theme),
            'type': theme_data.get('type', 'builtin'),
            'palette': theme_data.get('palette', 'light')
        }
    
    def create_custom_theme(self, name, colors):
        """Создание пользовательской темы"""
        try:
            themes_dir = self.get_themes_directory()
            theme_file = themes_dir / f"{name}.json"
            
            theme_data = {
                "name": name,
                "palette": "dark" if colors.get('background', '#FFFFFF').lower() in ['#000000', '#121212', '#1e1e1e'] else "light",
                "colors": colors
            }
            
            with open(theme_file, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, indent=2, ensure_ascii=False)
            
            # Перезагружаем темы
            self.load_themes()
            
            logger.info(f"Создана пользовательская тема: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания темы {name}: {e}")
            return False
    
    def delete_custom_theme(self, theme_name):
        """Удаление пользовательской темы"""
        try:
            if theme_name not in self.themes:
                return False
            
            theme_data = self.themes[theme_name]
            if theme_data.get('type') != 'custom':
                return False
            
            theme_file = theme_data.get('file')
            if not theme_file or not os.path.exists(theme_file):
                return False
            
            # Удаляем файл
            os.remove(theme_file)
            
            # Удаляем из списка тем
            del self.themes[theme_name]
            
            # Если удаляемая тема была текущей, переключаемся на светлую
            if theme_name == self.current_theme:
                self.set_theme("light")
            
            logger.info(f"Удалена пользовательская тема: {theme_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления темы {theme_name}: {e}")
            return False
    
    # Методы для получения стилей тем
    
    def get_light_styles(self):
        """Стили светлой темы"""
        return {
            "QPushButton#connectBtn": {
                "background-color": "#4CAF50",
                "color": "white",
                "font-size": "14px"
            },
            "QPushButton#connectBtn:hover": {
                "background-color": "#45a049"
            },
            "QPushButton#refreshBtn": {
                "background-color": "#2196F3",
                "color": "white"
            },
            "QPushButton#refreshBtn:hover": {
                "background-color": "#1976d2"
            }
        }
    
    def get_dark_styles(self):
        """Стили темной темы"""
        return {
            "QWidget": {
                "background-color": "#1e1e1e",
                "color": "#ffffff"
            },
            "QPushButton": {
                "background-color": "#2d2d2d",
                "color": "#ffffff",
                "border": "1px solid #3d3d3d"
            },
            "QPushButton:hover": {
                "background-color": "#3d3d3d"
            },
            "QPushButton#connectBtn": {
                "background-color": "#4CAF50",
                "color": "white"
            },
            "QPushButton#connectBtn:hover": {
                "background-color": "#45a049"
            },
            "QLineEdit, QTextEdit": {
                "background-color": "#2d2d2d",
                "color": "#ffffff",
                "border": "1px solid #3d3d3d"
            },
            "QListWidget": {
                "background-color": "#2d2d2d",
                "color": "#ffffff",
                "border": "1px solid #3d3d3d"
            }
        }
    
    def get_blue_styles(self):
        """Стили синей темы"""
        return {
            "QPushButton": {
                "background-color": "#1976d2",
                "color": "white",
                "border-radius": "4px"
            },
            "QPushButton:hover": {
                "background-color": "#1565c0"
            },
            "QLineEdit:focus, QTextEdit:focus": {
                "border": "2px solid #1976d2"
            },
            "QTabBar::tab:selected": {
                "border-bottom": "2px solid #1976d2"
            }
        }
    
    def get_midnight_styles(self):
        """Стили полуночной темы"""
        return {
            "QWidget": {
                "background-color": "#0a0a14",
                "color": "#e0e0ff"
            },
            "QPushButton": {
                "background-color": "#1a1a2e",
                "color": "#e0e0ff",
                "border": "1px solid #2a2a3e"
            },
            "QPushButton:hover": {
                "background-color": "#2a2a3e"
            },
            "QLineEdit, QTextEdit": {
                "background-color": "#1a1a2e",
                "color": "#e0e0ff",
                "border": "1px solid #2a2a3e"
            }
        }


# Глобальный экземпляр
_theme_manager_instance = None

def get_theme_manager() -> ThemeManager:
    """Получение глобального экземпляра ThemeManager"""
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance


def init_theme():
    """Инициализация темы при запуске приложения"""
    theme_manager = get_theme_manager()
    theme_manager.apply_theme()
    return theme_manager


# Тестирование
if __name__ == "__main__":
    print("🧪 Тестирование менеджера тем...")
    
    # Создаем приложение для тестирования
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Тестируем менеджер тем
    manager = get_theme_manager()
    
    print(f"\n📋 Доступные темы ({len(manager.themes)}):")
    themes = manager.get_available_themes()
    for theme in themes:
        current = " (текущая)" if theme['current'] else ""
        print(f"  {theme['id']}: {theme['name']} ({theme['type']}){current}")
    
    print(f"\n🎨 Текущая тема: {manager.current_theme}")
    
    # Информация о текущей теме
    current_info = manager.get_current_theme_info()
    if current_info:
        print(f"  Имя: {current_info['name']}")
        print(f"  Тип: {current_info['type']}")
        print(f"  Палитра: {current_info['palette']}")
    
    # Тест создания пользовательской темы
    print("\n🎨 Тест создания пользовательской темы...")
    
    custom_colors = {
        "primary": "#9C27B0",
        "secondary": "#BA68C8",
        "accent": "#7B1FA2",
        "background": "#121212",
        "surface": "#1E1E1E",
        "text_primary": "#E1E1E1",
        "text_secondary": "#AAAAAA",
        "border": "#2D2D2D"
    }
    
    success = manager.create_custom_theme("test_purple", custom_colors)
    print(f"  Создана тема 'test_purple': {success}")
    
    # Тест переключения тем
    print("\n🔄 Тест переключения тем...")
    
    test_themes = ["dark", "blue", "light"]
    for theme in test_themes:
        if theme in manager.themes:
            success = manager.set_theme(theme)
            print(f"  Переключение на '{theme}': {'✅' if success else '❌'}")
    
    # Возвращаемся к светлой теме
    manager.set_theme("light")
    
    # Тест удаления пользовательской темы
    print("\n🗑️ Тест удаления пользовательской темы...")
    success = manager.delete_custom_theme("test_purple")
    print(f"  Удалена тема 'test_purple': {success}")
    
    print("\n✅ Тест завершен!")