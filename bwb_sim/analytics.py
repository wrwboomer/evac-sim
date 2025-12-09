# FILE: bwb_sim/analytics.py
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import datetime
import sys
from .engine import Simulation

class AnalyticsDashboard(ttk.Frame):
    def __init__(self, parent, controller, config, baseline_data=None, baseline_name=None):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.config = config
        self.is_running = False
        self.results = []
        
        # Load from controller memory
        self.baseline_results = baseline_data
        self.baseline_name = baseline_name
        
        self.create_widgets()
        
        # If we have baseline data, show the charts immediately and enable Clear button
        if self.baseline_results:
            self.btn_clear.config(state="normal")
            self.render_charts()

    def create_widgets(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=X, pady=(0, 20))
        
        ac_name = self.config.lopa.name
        ttk.Label(top_frame, text=f"Batch Analytics: {ac_name}", font=("Helvetica", 18, "bold"), bootstyle="primary").pack(side=LEFT)
        
        ctrl_frame = ttk.Labelframe(self, text="Run Settings", padding=15, bootstyle="info")
        ctrl_frame.pack(fill=X, pady=5)
        
        f1 = ttk.Frame(ctrl_frame)
        f1.pack(fill=X)
        
        ttk.Label(f1, text="Number of Trials:", font=("Helvetica", 12)).pack(side=LEFT, padx=5)
        self.trials_var = tk.IntVar(value=50)
        ttk.Spinbox(f1, from_=5, to=500, textvariable=self.trials_var, width=10).pack(side=LEFT, padx=5)
        
        self.btn_run = ttk.Button(f1, text="▶ RUN BATCH ANALYSIS", command=self.start_batch_run, bootstyle="success")
        self.btn_run.pack(side=LEFT, padx=20)
        
        # --- BASELINE CONTROLS ---
        # Clear Button (Rightmost)
        self.btn_clear = ttk.Button(f1, text="✖ CLEAR BASELINE", command=self.clear_baseline, bootstyle="secondary-outline", state="disabled")
        self.btn_clear.pack(side=RIGHT, padx=5)

        # Set Button
        self.btn_baseline = ttk.Button(f1, text="📌 SET AS BASELINE", command=self.set_baseline, bootstyle="warning-outline", state="disabled")
        self.btn_baseline.pack(side=RIGHT, padx=5)
        # -------------------------
        
        self.progress = ttk.Progressbar(ctrl_frame, orient=HORIZONTAL, mode='determinate', bootstyle="striped")
        self.progress.pack(fill=X, pady=(10, 0))
        
        self.lbl_stats = ttk.Label(ctrl_frame, text="Ready. Click Run to start.", font=("Consolas", 10), bootstyle="secondary")
        self.lbl_stats.pack(fill=X, pady=5)

        self.plot_frame = ttk.Frame(self, bootstyle="light")
        self.plot_frame.pack(fill=BOTH, expand=True, pady=10)
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(10, 5))
        self.fig.patch.set_facecolor('#ffffff')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(side=BOTTOM, fill=X)

        ttk.Button(btn_frame, text="EXIT APP", command=self.quit_app, bootstyle="danger-outline").pack(side=LEFT)
        ttk.Button(btn_frame, text="SIMULATION SETUP (BACK)", command=self.go_back, bootstyle="secondary").pack(side=RIGHT, padx=5)
        self.btn_save = ttk.Button(btn_frame, text="SAVE REPORT", command=self.save_report, bootstyle="info", state="disabled")
        self.btn_save.pack(side=RIGHT, padx=5)
        self.btn_view = ttk.Button(btn_frame, text="VIEW REPORT", command=self.view_report, bootstyle="primary", state="disabled")
        self.btn_view.pack(side=RIGHT, padx=5)

    def view_report(self):
        report_text = self.generate_report_text()
        if not report_text: return
        
        top = tk.Toplevel(self)
        top.title("Simulation Report")
        top.geometry("600x500")
        
        text_area = tk.Text(top, wrap="word", font=("Consolas", 10))
        text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)
        text_area.insert("1.0", report_text)
        text_area.config(state="disabled") # Read-only
        
        btn_close = ttk.Button(top, text="CLOSE", command=top.destroy, bootstyle="secondary")
        btn_close.pack(pady=5)

    def start_batch_run(self):
        if self.is_running: return
        self.is_running = True
        self.btn_run.config(state="disabled")
        self.btn_save.config(state="disabled")
        self.btn_view.config(state="disabled")
        self.btn_baseline.config(state="disabled")
        self.btn_clear.config(state="disabled")
        self.results = []
        self.progress['value'] = 0
        
        trials = self.trials_var.get()
        self.lbl_stats.config(text=f"Initializing {trials} simulations...", bootstyle="warning")
        
        threading.Thread(target=self.run_loop, args=(trials,), daemon=True).start()

    def run_loop(self, trials):
        try:
            for i in range(trials):
                sim = Simulation(self.config)
                stats = sim.run(headless=True)
                self.results.append(stats['total_time'] / 60.0) 
                
                pct = ((i + 1) / trials) * 100
                self.progress['value'] = pct
        except Exception as e:
            messagebox.showerror("Simulation Error", f"Batch Run Failed:\n{str(e)}")
            print(f"Batch Error: {e}")
            
        self.is_running = False
        self.after(0, self.render_charts)

    def set_baseline(self):
        if not self.results: return
        
        # Save locally
        self.baseline_results = list(self.results)
        self.baseline_name = self.config.lopa.name
        
        # Save Global
        self.controller.save_baseline_globally(self.baseline_results, self.baseline_name)
        
        self.btn_clear.config(state="normal") # Enable clear button
        self.render_charts()

    def clear_baseline(self):
        """Wipes the baseline data and refreshes charts."""
        self.baseline_results = None
        self.baseline_name = None
        
        # Clear Global
        self.controller.save_baseline_globally(None, None)
        
        self.btn_clear.config(state="disabled")
        self.render_charts()

    def render_charts(self):
        self.btn_run.config(state="normal")
        if self.results:
            self.btn_save.config(state="normal")
            self.btn_view.config(state="normal")
            self.btn_baseline.config(state="normal")
        
        if self.baseline_results:
            self.btn_clear.config(state="normal")

        # Handle empty states
        if not self.results and self.baseline_results:
            current_times = np.array([])
            avg = 0
            p90 = 0
        elif self.results:
            current_times = np.array(self.results)
            avg = np.mean(current_times)
            p90 = np.percentile(current_times, 90)
        else:
            # Nothing to show at all (Cleared and no new run)
            self.ax1.clear()
            self.ax2.clear()
            self.lbl_stats.config(text="Ready.", bootstyle="secondary")
            self.canvas.draw()
            return 

        stats_text = ""
        if self.results:
            stats_text = f"CURRENT: Avg: {avg:.1f}m | 90th%: {p90:.1f}m"
        
        if self.baseline_results and self.results:
            base_avg = np.mean(self.baseline_results)
            delta = avg - base_avg
            sign = "+" if delta > 0 else ""
            stats_text += f" || vs BASELINE: {sign}{delta:.1f}m"
            
        self.lbl_stats.config(text=stats_text, bootstyle="success" if self.results else "secondary")
        
        # PLOT 1
        self.ax1.clear()
        
        if self.baseline_results:
            lbl = self.baseline_name[:15] + "..." if self.baseline_name else "Baseline"
            self.ax1.hist(self.baseline_results, bins=10, color='#95a5a6', alpha=0.5, label=lbl)
            self.ax1.axvline(np.mean(self.baseline_results), color='gray', linestyle='dashed', linewidth=1)

        if self.results:
            self.ax1.hist(current_times, bins=10, color='#007acc', alpha=0.7, label='Current', edgecolor='black')
            self.ax1.axvline(avg, color='red', linestyle='dashed', linewidth=1, label=f'Avg: {avg:.1f}m')
        
        self.ax1.set_title("Distribution Comparison")
        self.ax1.set_xlabel("Time (Minutes)")
        self.ax1.set_ylabel("Frequency")
        self.ax1.legend()

        # PLOT 2
        self.ax2.clear()
        
        data_to_plot = []
        labels = []
        colors = []
        
        if self.baseline_results:
            data_to_plot.append(self.baseline_results)
            lbl = self.baseline_name[:12] + "..." if self.baseline_name else "Baseline"
            labels.append(lbl)
            colors.append('#95a5a6')
            
        if self.results:
            data_to_plot.append(current_times)
            labels.append(self.config.lopa.name[:12]+"...")
            colors.append('#007acc')

        if data_to_plot:
            bplot = self.ax2.boxplot(data_to_plot, patch_artist=True, labels=labels)
            for patch, color in zip(bplot['boxes'], colors):
                patch.set_facecolor(color)
            
        self.ax2.set_title("Variance Comparison")
        self.ax2.set_ylabel("Minutes")
        self.ax2.grid(True, axis='y', linestyle='--', alpha=0.7)

        self.canvas.draw()

    def generate_report_text(self):
        if not self.results: return ""
        
        times = np.array(self.results)
        avg = np.mean(times)
        min_t = np.min(times)
        max_t = np.max(times)
        std_dev = np.std(times)
        
        lines = []
        lines.append("==========================================")
        lines.append("       BWB BATCH SIMULATION REPORT        ")
        lines.append("==========================================")
        lines.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"Layout:           {self.config.lopa.name}")
        lines.append(f"Strategy:         {self.config.strategy}")
        lines.append(f"Doors Used:       {self.config.primary_door}")
        lines.append(f"Total Trials:     {len(self.results)}")
        lines.append("")
        lines.append("--- STATISTICS (Minutes) ---")
        lines.append(f"Average Time:     {avg:.2f} min")
        lines.append(f"Fastest Time:     {min_t:.2f} min")
        lines.append(f"Slowest Time:     {max_t:.2f} min")
        lines.append(f"Std Deviation:    {std_dev:.2f} min")
        
        if self.baseline_results:
            base_times = np.array(self.baseline_results)
            base_avg = np.mean(base_times)
            delta = avg - base_avg
            pct_diff = (delta / base_avg) * 100
            
            lines.append("")
            lines.append("--- COMPARISON ANALYSIS ---")
            lines.append(f"Baseline Aircraft: {self.baseline_name}")
            lines.append(f"Baseline Avg Time: {base_avg:.2f} min")
            lines.append(f"Current Avg Time:  {avg:.2f} min")
            lines.append(f"Time Difference:   {delta:+.2f} min")
            
            perf_str = "Slower" if delta > 0 else "Faster"
            lines.append(f"Performance:       {abs(pct_diff):.1f}% {perf_str}")
            
        lines.append("==========================================")
        return "\n".join(lines)

    def save_report(self):
        report_text = self.generate_report_text()
        if not report_text: return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            try:
                with open(file_path, "w") as f: f.write(report_text)
                messagebox.showinfo("Success", "Batch report saved.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def go_back(self):
        self.controller.show_config()

    def quit_app(self):
        self.controller.destroy()
        sys.exit()