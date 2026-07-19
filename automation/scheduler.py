import json
import logging
import os
import threading
from datetime import datetime

from utils import app_dir

CONFIG_PATH = os.path.join(app_dir(), 'results', 'automation.json')

TASK_DEFAULTS = {
    'auto_scan': {
        'enabled': False,
        'interval_min': 30,
    },
    'monitor_positions': {
        'enabled': False,
        'interval_min': 5,
        'autostart': False,
    },
    'refresh_watchlist': {
        'enabled': False,
        'interval_min': 10,
    },
    'auto_news_scan': {
        'enabled': False,
        'interval_min': 15,
    },
    'check_pending_trades': {
        'enabled': True,
        'interval_min': 5,
        'autostart': True,
    },
}


class AutomationTask:
    def __init__(self, name, interval_min, callback, enabled=False):
        self.name = name
        self.interval_min = interval_min
        self.callback = callback
        self.enabled = enabled
        self._running = False
        self._after_id = None
        self._last_run = None
        self._last_result = ''
        self._run_count = 0

    @property
    def is_running(self):
        return self._running

    @property
    def last_run(self):
        return self._last_run

    @property
    def last_result(self):
        return self._last_result

    @property
    def run_count(self):
        return self._run_count

    def next_run_seconds(self, root):
        if not self._running or self._after_id is None:
            return None
        return self.interval_min * 60


class AutomationScheduler:
    def __init__(self, root):
        self.root = root
        self._tasks: dict[str, AutomationTask] = {}
        self._config = {}
        self._on_status_change = None
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception:
                self._config = {}
        else:
            self._config = {}

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        data = {}
        for name, task in self._tasks.items():
            data[name] = {
                'enabled': task.enabled,
                'interval_min': task.interval_min,
            }
        if 'monitor_positions' in data:
            data['monitor_positions']['autostart'] = self._config.get(
                'monitor_positions', {}).get('autostart', False)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def register_task(self, name, callback, interval_min=None, enabled=None):
        defaults = TASK_DEFAULTS.get(name, {'enabled': False, 'interval_min': 30})
        cfg = self._config.get(name, {})
        interval = interval_min or cfg.get('interval_min', defaults['interval_min'])
        is_enabled = enabled if enabled is not None else cfg.get('enabled', defaults['enabled'])
        task = AutomationTask(name, interval, callback, is_enabled)
        self._tasks[name] = task
        return task

    def get_task(self, name):
        return self._tasks.get(name)

    def get_all_tasks(self):
        return dict(self._tasks)

    def set_interval(self, name, minutes):
        task = self._tasks.get(name)
        if task:
            task.interval_min = minutes
            self.save_config()

    def set_enabled(self, name, enabled):
        task = self._tasks.get(name)
        if task:
            task.enabled = enabled
            self.save_config()

    def set_autostart_monitor(self, enabled):
        if 'monitor_positions' not in self._config:
            self._config['monitor_positions'] = {}
        self._config['monitor_positions']['autostart'] = enabled
        self.save_config()

    def get_autostart_monitor(self):
        return self._config.get('monitor_positions', {}).get('autostart', False)

    def start_task(self, name):
        task = self._tasks.get(name)
        if not task or task._running:
            return
        task._running = True
        task.enabled = True
        self.save_config()
        self._run_task(task)

    def stop_task(self, name):
        task = self._tasks.get(name)
        if not task:
            return
        task._running = False
        task.enabled = False
        if task._after_id is not None:
            try:
                self.root.after_cancel(task._after_id)
            except Exception:
                pass
            task._after_id = None
        self.save_config()
        self._notify_status()

    def start_all(self):
        for name, task in self._tasks.items():
            if task.enabled:
                self.start_task(name)

    def stop_all(self):
        for name, task in self._tasks.items():
            if task._running:
                task._running = False
                if task._after_id is not None:
                    try:
                        self.root.after_cancel(task._after_id)
                    except Exception:
                        pass
                    task._after_id = None

    def _run_task(self, task):
        if not task._running:
            return

        def do():
            try:
                result = task.callback()
                task._last_result = str(result) if result else 'OK'
            except Exception as e:
                task._last_result = f'Ошибка: {e}'
                logging.warning(f'Automation task {task.name} error: {e}')
            finally:
                task._last_run = datetime.now().strftime('%H:%M:%S')
                task._run_count += 1
                self._notify_status()

                if task._running:
                    task._after_id = self.root.after(
                        task.interval_min * 60_000,
                        lambda: self._run_task(task)
                    )

        t = threading.Thread(target=do, daemon=True)
        t.start()

    def run_task_now(self, name):
        task = self._tasks.get(name)
        if not task:
            return
        self._run_task(task)

    def set_status_callback(self, fn):
        self._on_status_change = fn

    def _notify_status(self):
        if self._on_status_change:
            try:
                self.root.after(0, self._on_status_change)
            except Exception:
                pass
