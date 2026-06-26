# notification_manager.py
import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Callable

from utils import app_dir

TRIGGER_TYPES = {
    'sl_hit': 'SL сработал',
    'tp_hit': 'TP сработал',
    'timeout': 'Таймаут позиции',
    'near_sl': 'Близко к SL',
    'near_tp': 'Близко к TP',
    'regime_change': 'Смена режима рынка',
    'drawdown_alert': 'Просадка превышена',
    'position_opened': 'Позиция открыта',
    'signal_detected': 'Новый сигнал',
    'price_alert': 'Ценовой алерт',
}

DEFAULT_TRIGGERS = {
    'sl_hit': True,
    'tp_hit': True,
    'timeout': True,
    'near_sl': True,
    'near_tp': False,
    'regime_change': True,
    'drawdown_alert': True,
    'position_opened': False,
    'signal_detected': True,
    'price_alert': True,
}

NOTIFY_FILE = os.path.join(app_dir(), 'results', 'notifications.json')


@dataclass
class Notification:
    timestamp: str
    trigger_type: str
    title: str
    message: str
    icon: str = 'info'
    acknowledged: bool = False

    @property
    def is_warning(self):
        return self.icon == 'warning'

    @property
    def is_error(self):
        return self.icon == 'error'


class NotificationManager:
    def __init__(self):
        self._triggers: dict = dict(DEFAULT_TRIGGERS)
        self._history: List[Notification] = []
        self._drawdown_threshold = 15.0
        self._near_distance_pct = 3.0
        self._toast_enabled = True
        self._sound_enabled = True
        self._callbacks: List[Callable] = []
        self._max_history = 500
        self._last_regime = None
        self.load_config()

    def load_config(self):
        if os.path.exists(NOTIFY_FILE):
            try:
                with open(NOTIFY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'triggers' in data:
                    self._triggers.update(data['triggers'])
                if 'drawdown_threshold' in data:
                    self._drawdown_threshold = data['drawdown_threshold']
                if 'near_distance_pct' in data:
                    self._near_distance_pct = data['near_distance_pct']
                if 'toast_enabled' in data:
                    self._toast_enabled = data['toast_enabled']
                if 'sound_enabled' in data:
                    self._sound_enabled = data['sound_enabled']
            except Exception:
                pass

    def save_config(self):
        os.makedirs(os.path.dirname(NOTIFY_FILE), exist_ok=True)
        data = {
            'triggers': self._triggers,
            'drawdown_threshold': self._drawdown_threshold,
            'near_distance_pct': self._near_distance_pct,
            'toast_enabled': self._toast_enabled,
            'sound_enabled': self._sound_enabled,
        }
        with open(NOTIFY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def triggers(self):
        return self._triggers

    @property
    def drawdown_threshold(self):
        return self._drawdown_threshold

    @drawdown_threshold.setter
    def drawdown_threshold(self, val):
        self._drawdown_threshold = val

    @property
    def near_distance_pct(self):
        return self._near_distance_pct

    @near_distance_pct.setter
    def near_distance_pct(self, val):
        self._near_distance_pct = val

    @property
    def toast_enabled(self):
        return self._toast_enabled

    @toast_enabled.setter
    def toast_enabled(self, val):
        self._toast_enabled = val

    @property
    def sound_enabled(self):
        return self._sound_enabled

    @sound_enabled.setter
    def sound_enabled(self, val):
        self._sound_enabled = val

    @property
    def history(self):
        return list(self._history)

    def add_callback(self, fn):
        self._callbacks.append(fn)

    def notify(self, trigger_type: str, title: str, message: str,
               icon: str = 'info'):
        if not self._triggers.get(trigger_type, False):
            return

        notif = Notification(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            trigger_type=trigger_type,
            title=title,
            message=message,
            icon=icon,
        )
        self._history.append(notif)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        if self._toast_enabled:
            from monitoring.toast import show_toast
            show_toast(title, message, icon=icon, duration=5)

        if self._sound_enabled:
            self._play_sound(trigger_type)

        for cb in self._callbacks:
            try:
                cb(notif)
            except Exception:
                pass

    def _play_sound(self, trigger_type):
        try:
            import winsound
            if trigger_type in ('sl_hit', 'drawdown_alert'):
                winsound.Beep(800, 300)
            elif trigger_type == 'tp_hit':
                winsound.Beep(1000, 200)
            elif trigger_type in ('regime_change', 'timeout'):
                winsound.Beep(600, 200)
            else:
                winsound.Beep(500, 150)
        except Exception:
            pass

    def check_alerts(self, alerts):
        for a in alerts:
            trigger_map = {
                'SL_CLOSE': 'sl_hit',
                'TP_CLOSE': 'tp_hit',
                'TIMEOUT': 'timeout',
                'NEAR_SL': 'near_sl',
                'NEAR_TP': 'near_tp',
            }
            trigger = trigger_map.get(a.alert_type)
            if trigger:
                icon = 'warning' if trigger in ('sl_hit', 'drawdown_alert') else 'info'
                self.notify(trigger, a.ticker or 'Уведомление', a.message, icon=icon)

    def check_regime_change(self, new_regime):
        if self._last_regime is not None and self._last_regime != new_regime:
            regime_labels = {
                'TRENDING_UP': 'Ростущий тренд',
                'TRENDING_DOWN': 'Падающий тренд',
                'RANGING': 'Боковик',
                'CRISIS': 'Кризис',
            }
            old_label = regime_labels.get(self._last_regime, self._last_regime)
            new_label = regime_labels.get(new_regime, new_regime)
            icon = 'warning' if new_regime in ('TRENDING_DOWN', 'CRISIS') else 'info'
            self.notify(
                'regime_change',
                'Смена режима рынка',
                f'{old_label} -> {new_label}',
                icon=icon,
            )
        self._last_regime = new_regime

    def check_drawdown(self, current_dd_pct):
        if current_dd_pct >= self._drawdown_threshold:
            self.notify(
                'drawdown_alert',
                'Просадка!',
                f'Текущая просадка {current_dd_pct:.1f}% превышает порог {self._drawdown_threshold:.1f}%',
                icon='warning',
            )

    def on_position_opened(self, ticker, side, entry_price):
        self.notify(
            'position_opened',
            f'{ticker} открыта позиция',
            f'{side} @ {entry_price:.2f}',
            icon='info',
        )

    def on_signal_detected(self, ticker, side, strategy, price=None):
        price_str = f' @ {price:.2f}' if price else ''
        self.notify(
            'signal_detected',
            f'Сигнал: {ticker} {side}',
            f'{strategy}{price_str}',
            icon='info',
        )

    def get_unacked(self):
        return [n for n in self._history if not n.acknowledged]

    def ack_all(self):
        for n in self._history:
            n.acknowledged = True

    def clear_history(self):
        self._history.clear()

    def get_trigger_config(self):
        return {
            'triggers': dict(self._triggers),
            'drawdown_threshold': self._drawdown_threshold,
            'near_distance_pct': self._near_distance_pct,
            'toast_enabled': self._toast_enabled,
            'sound_enabled': self._sound_enabled,
        }

    def set_trigger_config(self, config: dict):
        if 'triggers' in config:
            self._triggers.update(config['triggers'])
        if 'drawdown_threshold' in config:
            self._drawdown_threshold = config['drawdown_threshold']
        if 'near_distance_pct' in config:
            self._near_distance_pct = config['near_distance_pct']
        if 'toast_enabled' in config:
            self._toast_enabled = config['toast_enabled']
        if 'sound_enabled' in config:
            self._sound_enabled = config['sound_enabled']
        self.save_config()
