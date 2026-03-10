import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import sys

# Ensure Pyinstaller captures these modules statically
import main
import config
import email_sender
import news_fetcher
import schedule

# Dotenv setup
env_path = os.path.join(os.path.dirname(__file__), '.env')

# Default keys and values for .env explicitly mapped
default_env_keys = {
    "SMTP_SERVER": "smtp.office365.com",
    "SMTP_PORT": "587",
    "SENDER_EMAIL": "your_outlook_email@company.com",
    "SENDER_PASSWORD": "your_app_password_or_token",
    "RECEIVER_EMAIL": "receiver@domain.com",
    "FORWARD_EMAIL": "NONE",
    "SCHEDULE_TYPE": "once_daily",
    "CAT2_SENDER_EMAIL": "",
    "CAT2_SENDER_PASSWORD": "",
    "CAT2_RECEIVER_EMAIL": "",
    "CAT2_FORWARD_EMAIL": "NONE",
    "CAT2_SCHEDULE_TYPE": "once_daily",
    "LOG_LEVEL": "INFO"
}

def load_env():
    env_data = default_env_keys.copy()
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_data[k.strip()] = v.strip()
    return env_data

def save_env(env_data):
    # Save the dictionary back to .env
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# Environment Configuration for Python Mailing System\n")
        f.write("# Outlook SMTP Defaults: smtp.office365.com / 587\n\n")
        for k, v in env_data.items():
            f.write(f"{k}={v}\n")

class MailingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI News Mailing Control Panel")
        self.root.geometry("600x700")
        self.env_data = load_env()
        self.entries = {}
        self.main_process = None
        
        self.create_widgets()

    def create_widgets(self):
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="Environment Settings (.env)")
        config_frame.pack(fill="x", padx=10, pady=5)
        
        # Add Canvas and Scrollbar to handle many fields
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        for k, v in self.env_data.items():
            lbl = ttk.Label(scrollable_frame, text=k)
            lbl.grid(row=row, column=0, padx=5, pady=2, sticky="w")
            
            # Width ~40 but scrollable if text is longer
            ent_var = tk.StringVar(value=v)
            ent = ttk.Entry(scrollable_frame, textvariable=ent_var, width=45)
            ent.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
            
            self.entries[k] = ent_var
            row += 1

        # Buttons Frame
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_save = ttk.Button(btn_frame, text="Save Config", command=self.save_config)
        self.btn_save.pack(side="left", padx=5)
        
        self.btn_run = ttk.Button(btn_frame, text="Run Scheduler", command=self.run_system)
        self.btn_run.pack(side="left", padx=5)
        
        self.btn_stop = ttk.Button(btn_frame, text="Stop Scheduler", command=self.stop_system, state="disabled")
        self.btn_stop.pack(side="left", padx=5)
        
        self.btn_restart = ttk.Button(btn_frame, text="Restart", command=self.restart_system, state="disabled")
        self.btn_restart.pack(side="left", padx=5)
        
        self.status_var = tk.StringVar(value="Status: Stopped")
        status_lbl = ttk.Label(self.root, textvariable=self.status_var, foreground="blue")
        status_lbl.pack(pady=5)
        
        # Log Viewer Frame
        log_frame = ttk.LabelFrame(self.root, text="Application Logs")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, state='disabled', wrap='word', bg='black', fg='white')
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Periodically refresh logs
        self.log_position = 0
        self.update_logs()

    def save_config(self):
        for k in self.env_data.keys():
            self.env_data[k] = self.entries[k].get()
        save_env(self.env_data)
        messagebox.showinfo("Saved", "Configuration saved successfully!")

    def run_system(self):
        self.save_config() # Save before running
        
        # Reload the environment variables and the config module
        import config
        from dotenv import load_dotenv
        from importlib import reload
        load_dotenv(override=True)
        reload(config)
        import main
        import schedule
        import threading
        import time

        if not getattr(self, 'running', False):
            self.running = True
            self.btn_run.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.btn_restart.config(state="normal")
            self.status_var.set("Status: Running")
            
            def scheduler_loop():
                schedule.clear()
                main.setup_schedule()
                while self.running:
                    schedule.run_pending()
                    time.sleep(1)
            
            self.main_thread = threading.Thread(target=scheduler_loop, daemon=True)
            self.main_thread.start()

    def stop_system(self):
        self.running = False
        import schedule
        schedule.clear()
            
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_restart.config(state="disabled")
        self.status_var.set("Status: Stopped")

    def restart_system(self):
        self.stop_system()
        self.run_system()

    def update_logs(self):
        log_path = os.path.join(os.path.dirname(__file__), 'ai_news_mailing.log')
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    f.seek(self.log_position)
                    new_lines = f.read()
                    if new_lines:
                        self.log_position = f.tell()
                        self.log_text.config(state='normal')
                        self.log_text.insert(tk.END, new_lines)
                        self.log_text.see(tk.END)
                        self.log_text.config(state='disabled')
            except Exception as e:
                pass
        
        self.root.after(2000, self.update_logs)

if __name__ == "__main__":
    root = tk.Tk()
    app = MailingApp(root)
    root.mainloop()
