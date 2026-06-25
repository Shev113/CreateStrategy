# alerts.py
import logging
import platform

ALERT_TYPE_SL_CLOSE = 'sl_close'
ALERT_TYPE_TP_CLOSE = 'tp_close'
ALERT_TYPE_TIMEOUT = 'timeout'
ALERT_TYPE_NEAR_SL = 'near_sl'
ALERT_TYPE_NEAR_TP = 'near_tp'


class Alert:
    __slots__ = ('ticker', 'alert_type', 'message', 'entry_price',
                 'current_price', 'sl_price', 'tp_price', 'side')

    def __init__(self, ticker, alert_type, message, entry_price=0,
                 current_price=0, sl_price=0, tp_price=0, side=''):
        self.ticker = ticker
        self.alert_type = alert_type
        self.message = message
        self.entry_price = entry_price
        self.current_price = current_price
        self.sl_price = sl_price
        self.tp_price = tp_price
        self.side = side

    def __repr__(self):
        return f'Alert({self.ticker}, {self.alert_type}, {self.message})'


def play_beep(frequency=800, duration=300):
    if platform.system() == 'Windows':
        try:
            import winsound
            winsound.Beep(frequency, duration)
        except Exception:
            pass


def show_popup(root, title, message):
    try:
        import tkinter.messagebox as mb
        root.after(0, lambda: mb.showinfo(title, message))
    except Exception:
        logging.exception('Failed to show popup alert')


def format_alert_message(alert):
    side_map = {'LONG': 'ЛОНГ', 'SHORT': 'ШОРТ'}
    side_str = side_map.get(alert.side, alert.side)

    if alert.alert_type == ALERT_TYPE_SL_CLOSE:
        return (f'Срабатывание SL: {alert.ticker} ({side_str})\n'
                f'Цена входа: {alert.entry_price:.2f} → SL: {alert.sl_price:.2f}')
    elif alert.alert_type == ALERT_TYPE_TP_CLOSE:
        return (f'Срабатывание TP: {alert.ticker} ({side_str})\n'
                f'Цена входа: {alert.entry_price:.2f} → TP: {alert.tp_price:.2f}')
    elif alert.alert_type == ALERT_TYPE_TIMEOUT:
        return (f'Timeout: {alert.ticker} ({side_str})\n'
                f'Цена входа: {alert.entry_price:.2f} → текущая: {alert.current_price:.2f}')
    elif alert.alert_type == ALERT_TYPE_NEAR_SL:
        return (f'Близко к SL: {alert.ticker} ({side_str})\n'
                f'Текущая: {alert.current_price:.2f}, SL: {alert.sl_price:.2f}')
    elif alert.alert_type == ALERT_TYPE_NEAR_TP:
        return (f'Близко к TP: {alert.ticker} ({side_str})\n'
                f'Текущая: {alert.current_price:.2f}, TP: {alert.tp_price:.2f}')
    return alert.message
