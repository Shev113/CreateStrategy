import logging
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from cloud.sync import sync_manager, get_sync_files, is_encrypted_file, _load_cloud_meta, _VERIFICATION_CODE_REDIRECT
from cloud.oauth import start_oauth_flow, manual_code_flow, get_valid_token, load_token, delete_token


class CloudPanel:
    def __init__(self, parent, root):
        self.root = root
        self._syncing = False
        self._build_ui(parent)

    def _paste_to(self, var):
        try:
            text = self.root.clipboard_get()
            var.set(text)
        except tk.TclError:
            pass

    def _build_ui(self, parent):
        main = ttk.Frame(parent, padding=10)
        main.pack(fill='both', expand=True)

        status_frame = ttk.LabelFrame(main, text='Статус подключения', padding=10)
        status_frame.pack(fill='x', pady=(0, 5))

        self._status_var = tk.StringVar(value='Проверка...')
        self._status_label = ttk.Label(status_frame, textvariable=self._status_var,
                                        font=('Segoe UI', 10))
        self._status_label.pack(side='left', fill='x', expand=True)

        self._connect_btn = ttk.Button(status_frame, text='Подключить',
                                        command=self._on_connect)
        self._connect_btn.pack(side='right', padx=(10, 0))

        self._disconnect_btn = ttk.Button(status_frame, text='Отключить',
                                          command=self._on_disconnect, state='disabled')
        self._disconnect_btn.pack(side='right')

        settings_frame = ttk.LabelFrame(main, text='Настройки Яндекс.Диска', padding=10)
        settings_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(settings_frame, text='Client ID:').grid(row=0, column=0, sticky='w', pady=2)
        self._client_id_var = tk.StringVar(value=sync_manager.client_id)
        ttk.Entry(settings_frame, textvariable=self._client_id_var, width=45).grid(
            row=0, column=1, sticky='ew', padx=(5, 0), pady=2)
        ttk.Button(settings_frame, text='Вставить',
                   command=lambda: self._paste_to(self._client_id_var)).grid(
            row=0, column=2, padx=(3, 0), pady=2)

        ttk.Label(settings_frame, text='Client Secret:').grid(row=1, column=0, sticky='w', pady=2)
        self._client_secret_var = tk.StringVar(value=sync_manager.client_secret)
        ttk.Entry(settings_frame, textvariable=self._client_secret_var, width=45,
                  show='*').grid(row=1, column=1, sticky='ew', padx=(5, 0), pady=2)
        ttk.Button(settings_frame, text='Вставить',
                   command=lambda: self._paste_to(self._client_secret_var)).grid(
            row=1, column=2, padx=(3, 0), pady=2)

        ttk.Label(settings_frame, text='Код подтверждения:').grid(row=2, column=0, sticky='w', pady=2)
        code_frame = ttk.Frame(settings_frame)
        code_frame.grid(row=2, column=1, sticky='ew', padx=(5, 0), pady=2)
        self._code_var = tk.StringVar()
        code_entry = ttk.Entry(code_frame, textvariable=self._code_var, width=30)
        code_entry.pack(side='left', fill='x', expand=True)
        ttk.Button(code_frame, text='Вставить',
                   command=lambda: self._paste_to(self._code_var)).pack(side='left', padx=(3, 0))
        self._connect_code_btn = ttk.Button(code_frame, text='Подключить по коду',
                                            command=self._on_connect_manual)
        self._connect_code_btn.pack(side='left', padx=(3, 0))

        ttk.Label(settings_frame, text='Пароль шифрования:').grid(row=3, column=0, sticky='w', pady=2)
        self._password_var = tk.StringVar(value=sync_manager.sync_password)
        ttk.Entry(settings_frame, textvariable=self._password_var, width=45,
                  show='*').grid(row=3, column=1, sticky='ew', padx=(5, 0), pady=2)
        ttk.Button(settings_frame, text='Вставить',
                   command=lambda: self._paste_to(self._password_var)).grid(
            row=3, column=2, padx=(3, 0), pady=2)

        self._auto_sync_var = tk.BooleanVar(value=sync_manager.auto_sync_on_close)
        ttk.Checkbutton(settings_frame, text='Автосинк при закрытии приложения',
                         variable=self._auto_sync_var).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(5, 0))

        ttk.Button(settings_frame, text='Сохранить настройки',
                    command=self._save_settings).grid(
            row=4, column=0, columnspan=2, pady=(10, 0))

        settings_frame.columnconfigure(1, weight=1)

        help_frame = ttk.LabelFrame(main, text='Инструкция', padding=10)
        help_frame.pack(fill='x', pady=(0, 5))

        row1 = ttk.Frame(help_frame)
        row1.pack(anchor='w')
        ttk.Label(row1, text='1. Откройте ', font=('Segoe UI', 9),
                  foreground='gray').pack(side='left')
        link1 = tk.Label(row1, text='https://oauth.yandex.ru/', font=('Segoe UI', 9, 'underline'),
                         foreground='#4a90d9', cursor='hand2')
        link1.pack(side='left')
        link1.bind('<Button-1>', lambda e: self._open_url('https://oauth.yandex.ru/'))

        ttk.Label(help_frame, text='2. Зарегистрируйте приложение (Веб-сервисы), Redirect URI установится автоматически',
                  font=('Segoe UI', 9), foreground='gray', justify='left').pack(anchor='w')
        ttk.Label(help_frame, text='3. Дайте доступ: Яндекс.Диск (чтение/запись)',
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')
        ttk.Label(help_frame, text='4. Скопируйте Client ID и Client Secret выше',
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')
        ttk.Label(help_frame, text='5. Нажмите "Подключить", подтвердите доступ на Яндексе,',
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')
        ttk.Label(help_frame, text='   скопируйте код и вставьте в поле "Код подтверждения"',
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')

        actions_frame = ttk.LabelFrame(main, text='Синхронизация', padding=10)
        actions_frame.pack(fill='x', pady=(0, 5))

        btn_row = ttk.Frame(actions_frame)
        btn_row.pack(fill='x')

        self._upload_btn = ttk.Button(btn_row, text='Загрузить в облако',
                                       command=lambda: self._run_sync('upload'))
        self._upload_btn.pack(side='left', padx=(0, 5))

        self._download_btn = ttk.Button(btn_row, text='Скачать из облака',
                                         command=lambda: self._run_sync('download'))
        self._download_btn.pack(side='left', padx=(0, 5))

        self._sync_btn = ttk.Button(btn_row, text='Двусторонний синк',
                                      command=lambda: self._run_sync('bidir'))
        self._sync_btn.pack(side='left')

        self._progress_var = tk.StringVar(value='')
        ttk.Label(actions_frame, textvariable=self._progress_var,
                  font=('Segoe UI', 9)).pack(anchor='w', pady=(10, 0))

        self._progress_bar = ttk.Progressbar(actions_frame, mode='determinate')
        self._progress_bar.pack(fill='x', pady=(5, 0))

        self._result_var = tk.StringVar(value='')
        self._result_label = ttk.Label(actions_frame, textvariable=self._result_var,
                                         font=('Segoe UI', 9), foreground='#4CAF50')
        self._result_label.pack(anchor='w', pady=(5, 0))

        files_frame = ttk.LabelFrame(main, text='Файлы', padding=10)
        files_frame.pack(fill='both', expand=True, pady=(0, 0))

        cols = ('Файл', 'Шифр', 'Лок.', 'Обл.', 'Последний синк')
        self._files_tree = ttk.Treeview(files_frame, columns=cols, show='headings', height=8)
        for c in cols:
            self._files_tree.heading(c, text=c)
            self._files_tree.column(c, width=100, minwidth=60)
        self._files_tree.column('Файл', width=160)
        self._files_tree.column('Последний синк', width=140)

        vsb = ttk.Scrollbar(files_frame, orient='vertical', command=self._files_tree.yview)
        self._files_tree.configure(yscrollcommand=vsb.set)
        self._files_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._refresh_status()
        self._refresh_files_list()

    def _open_url(self, url):
        webbrowser.open(url)

    def _refresh_status(self):
        token = load_token()
        if token and token.get('access_token'):
            self._status_var.set('Подключено к Яндекс.Диску')
            self._connect_btn.config(state='disabled')
            self._connect_code_btn.config(state='disabled')
            self._disconnect_btn.config(state='normal')
            self._upload_btn.config(state='normal')
            self._download_btn.config(state='normal')
            self._sync_btn.config(state='normal')
        else:
            self._status_var.set('Не подключено')
            self._connect_btn.config(state='normal')
            self._connect_code_btn.config(state='normal')
            self._disconnect_btn.config(state='disabled')
            self._upload_btn.config(state='disabled')
            self._download_btn.config(state='disabled')
            self._sync_btn.config(state='disabled')

    def _refresh_files_list(self):
        for item in self._files_tree.get_children():
            self._files_tree.delete(item)

        meta = _load_cloud_meta()
        import os
        from utils import app_dir
        results_dir = os.path.join(app_dir(), 'results')

        for name in get_sync_files():
            enc = 'Да' if is_encrypted_file(name) else 'Нет'
            local_path = os.path.join(results_dir, name)
            local_exists = 'Да' if os.path.exists(local_path) else 'Нет'
            cloud_info = meta.get(name, {})
            last_sync = ''
            if cloud_info.get('last_sync'):
                try:
                    last_sync = time.strftime('%Y-%m-%d %H:%M:%S',
                                               time.localtime(cloud_info['last_sync']))
                except Exception:
                    last_sync = '?'
            cloud_exists = 'Да' if cloud_info.get('remote_name') else 'Нет'
            self._files_tree.insert('', 'end', values=(name, enc, local_exists, cloud_exists, last_sync))

    def _on_connect(self):
        cid = self._client_id_var.get().strip()
        csecret = self._client_secret_var.get().strip()
        if not cid or not csecret:
            messagebox.showwarning('Внимание',
                                    'Укажите Client ID и Client Secret в настройках')
            return

        self._save_settings()

        def do_connect():
            try:
                result, err = start_oauth_flow()
                self.root.after(0, self._on_connect_done, result, err)
            except Exception as e:
                logging.error(f'OAuth error: {e}')
                self.root.after(0, self._on_connect_done, False, str(e))

        threading.Thread(target=do_connect, daemon=True).start()
        self._status_var.set('Ожидание авторизации...')
        self._connect_btn.config(state='disabled')

    def _on_connect_manual(self):
        cid = self._client_id_var.get().strip()
        csecret = self._client_secret_var.get().strip()
        if not cid or not csecret:
            messagebox.showwarning('Внимание',
                                    'Укажите Client ID и Client Secret в настройках')
            return

        code = self._code_var.get().strip()
        if not code:
            messagebox.showwarning('Внимание',
                                    'Введите код подтверждения')
            return

        self._save_settings()

        def do_connect():
            try:
                result, err = manual_code_flow(code)
                self.root.after(0, self._on_connect_done, result, err)
            except Exception as e:
                logging.error(f'Manual OAuth error: {e}')
                self.root.after(0, self._on_connect_done, False, str(e))

        threading.Thread(target=do_connect, daemon=True).start()
        self._status_var.set('Подключение по коду...')
        self._connect_code_btn.config(state='disabled')

    def _show_error_dialog(self, title, message, details=''):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry('500x250')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text=message, wraplength=460, justify='left',
                  font=('Segoe UI', 10)).pack(anchor='w', pady=(0, 10))

        if details:
            text = tk.Text(frame, height=4, wrap='word', font=('Consolas', 9),
                           relief='solid', borderwidth=1)
            text.insert('1.0', details)
            text.config(state='disabled')
            text.pack(fill='x', pady=(0, 10))

            btn_frame = ttk.Frame(frame)
            btn_frame.pack(fill='x')

            ttk.Button(btn_frame, text='📋 Копировать ошибку',
                       command=lambda: self._copy_error(details, win)).pack(side='left', padx=(0, 5))

        ttk.Button(frame, text='Закрыть',
                   command=win.destroy).pack()

    def _copy_error(self, text, win=None):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        if win:
            win.destroy()

    def _on_connect_done(self, success, error_msg=''):
        if success:
            self._status_var.set('Подключено к Яндекс.Диску')
            self._connect_btn.config(state='disabled')
            self._connect_code_btn.config(state='disabled')
            self._disconnect_btn.config(state='normal')
            self._upload_btn.config(state='normal')
            self._download_btn.config(state='normal')
            self._sync_btn.config(state='normal')
            self._code_var.set('')
        else:
            self._status_var.set('Авторизация не удалась')
            self._connect_btn.config(state='normal')
            self._connect_code_btn.config(state='normal')
            if error_msg:
                self._show_error_dialog(
                    'Ошибка авторизации',
                    'Яндекс вернул ошибку. Скопируйте текст ниже и предоставьте его разработчику:',
                    error_msg)
            else:
                self._show_error_dialog(
                    'Авторизация',
                    'Открыта страница Яндекс OAuth.\n\n'
                    'После подтверждения доступа на странице Яндекса\n'
                    'вы увидите код подтверждения.\n\n'
                    'Скопируйте его и вставьте в поле "Код подтверждения",\n'
                    'затем нажмите "Подключить по коду".')
        self._refresh_files_list()

    def _on_disconnect(self):
        if messagebox.askyesno('Отключить', 'Удалить токен Яндекс.Диска?'):
            sync_manager.disconnect()
            self._refresh_status()
            self._refresh_files_list()

    def _save_settings(self):
        sync_manager.client_id = self._client_id_var.get().strip()
        sync_manager.client_secret = self._client_secret_var.get().strip()
        sync_manager.sync_password = self._password_var.get()
        sync_manager.auto_sync_on_close = self._auto_sync_var.get()
        sync_manager.save_config()
        self._refresh_status()

    def _run_sync(self, mode: str):
        if self._syncing:
            return
        self._syncing = True
        self._result_var.set('')
        self._progress_bar['value'] = 0
        self._set_buttons_state('disabled')

        def do_sync():
            try:
                def on_progress(name, current, total):
                    self.root.after(0, self._update_progress, name, current, total)

                if mode == 'upload':
                    result = sync_manager.upload_all(on_progress)
                elif mode == 'download':
                    result = sync_manager.download_all(on_progress)
                else:
                    result = sync_manager.sync_bidirectional(on_progress)

                self.root.after(0, self._sync_done, result)
            except Exception as e:
                logging.error(f'Sync error: {e}')
                from cloud.sync import SyncResult
                r = SyncResult()
                r.errors.append(str(e))
                self.root.after(0, self._sync_done, r)

        threading.Thread(target=do_sync, daemon=True).start()

    def _update_progress(self, name, current, total):
        self._progress_var.set(f'{current}/{total}: {name}')
        if total > 0:
            self._progress_bar['value'] = (current / total) * 100

    def _sync_done(self, result):
        self._syncing = False
        self._set_buttons_state('normal')
        self._progress_bar['value'] = 100

        summary = result.summary()
        color = '#f44336' if result.errors else '#4CAF50'
        self._result_var.set(summary)
        self._result_label.config(foreground=color)

        if result.conflicts:
            conflict_names = ', '.join(result.conflicts)
            self.root.after(100, lambda: messagebox.showwarning(
                'Конфликты',
                f'Обнаружены конфликты (изменены локально и в облаке):\n{conflict_names}\n\n'
                f'Используйте загрузку/скачивание для разрешения.'))

        self._refresh_files_list()

    def _set_buttons_state(self, state):
        if not self._syncing or state == 'normal':
            token = load_token()
            if token and token.get('access_token') and state == 'normal':
                self._upload_btn.config(state=state)
                self._download_btn.config(state=state)
                self._sync_btn.config(state=state)
            else:
                self._upload_btn.config(state='disabled')
                self._download_btn.config(state='disabled')
                self._sync_btn.config(state='disabled')
        else:
            self._upload_btn.config(state=state)
            self._download_btn.config(state=state)
            self._sync_btn.config(state='disabled')
