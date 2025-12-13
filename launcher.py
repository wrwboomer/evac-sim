# FILE: launcher.py
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import os
import sys
import glob
import shutil
import traceback
import math

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation
from bwb_sim.live_viz import LiveSimulationFrame
from bwb_sim.analytics import AnalyticsDashboard

class BWBApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="cosmo") 
        self.title("BWB Simulation Suite")
        self.geometry("800x980") 
        
        self.global_baseline_results = None
        self.global_baseline_name = None

        self.container = ttk.Frame(self)
        self.container.pack(fill=BOTH, expand=True)
        
        self.notebook = ttk.Notebook(self.container)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        self.setup_tabs()

    def setup_tabs(self):
        self.tab_config = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_config, text=" Simulation Setup ")
        self.config_page = ConfigPage(self.tab_config, self)
        self.config_page.pack(fill=BOTH, expand=True)
        
        self.tab_analytics = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_analytics, text=" Analytics & Batch Run ")
        
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

    def on_tab_change(self, event):
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            if selected_tab == 1: # Analytics
                for widget in self.tab_analytics.winfo_children(): widget.destroy()
                current_cfg = self.config_page.get_current_config()
                self.analytics_page = AnalyticsDashboard(
                    self.tab_analytics, 
                    self, 
                    current_cfg,
                    baseline_data=self.global_baseline_results,
                    baseline_name=self.global_baseline_name
                )
                self.analytics_page.pack(fill=BOTH, expand=True)
        except Exception as e:
            err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
            tk.messagebox.showerror("Tab Error", f"Failed to load Analytics Tab:\n\n{err_msg}")

    def save_baseline_globally(self, results, name):
        self.global_baseline_results = results
        self.global_baseline_name = name

    def show_config(self):
        self.notebook.select(0)

    def start_simulation(self, config):
        for widget in self.container.winfo_children(): 
            if widget != self.notebook: widget.destroy()
        
        self.notebook.pack_forget()
        
        sim = Simulation(config)
        self.current_frame = LiveSimulationFrame(self.container, sim, on_new_sim_callback=self.restore_tabs)
        self.current_frame.pack(fill=BOTH, expand=True)

    def restore_tabs(self):
        if self.current_frame: self.current_frame.destroy()
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.notebook.select(0)

class ConfigPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=30)
        self.controller = controller
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.layouts_dir = os.path.join(base_path, "layouts")
        
        self.available_loplas = glob.glob(os.path.join(self.layouts_dir, "*.json"))
        if not self.available_loplas: sys.exit(1)
        
        self.current_lopa_path = self.available_loplas[0]
        self.base_config = SimConfig.from_json(self.current_lopa_path)
        self.create_widgets()

    def create_widgets(self):
        # HEADER
        ttk.Label(self, text="SIMULATION CONFIGURATION", font="-size 14 -weight bold").pack(pady=10)
        
        # --- SECTION 2: LAYOUT ---
        self.lopa_frame = ttk.Labelframe(self, text="Aircraft Layout", padding=10, bootstyle="success")
        self.lopa_frame.pack(fill=X, pady=5)
        lopa_names = [os.path.basename(f) for f in self.available_loplas]
        self.lopa_var = tk.StringVar(value=lopa_names[0])
        cb = ttk.Combobox(self.lopa_frame, textvariable=self.lopa_var, values=lopa_names, state="readonly")
        cb.pack(fill=X)
        cb.bind("<<ComboboxSelected>>", self.reload_config)

        # --- SECTION 2B: EGRESS PARAMETERS (ALWAYS VISIBLE) ---
        self.egress_frame = ttk.Labelframe(self, text="Emergency Egress Parameters", padding=10, bootstyle="danger")
        self.egress_frame.pack(fill=X, pady=5)
        
        # 1. Door Blocking (50% Rule)
        lbl = ttk.Label(self.egress_frame, text="Active Exits (Uncheck to Block):")
        lbl.pack(anchor=W)
        self.door_chk_frame = ttk.Frame(self.egress_frame)
        self.door_chk_frame.pack(fill=X, pady=5)
        self.door_vars = {} # {name: BooleanVar}
        self.refresh_door_checkboxes() # Helper to populate

        # 2. Visibility
        self.add_manual_slider(self.egress_frame, "Visibility Factor (1=Clear, 0.5=Smoke)", "visibility_factor", 0.1, 1.0, initial=1.0, label_width=40)

        # 3. Slide Delay
        self.add_manual_slider(self.egress_frame, "Slide Delay (sec)", "slide_delay_sec", 0.0, 15.0, initial=10.0)
        
        # 4. Reaction & Panic (Moved/Copied)
        self.add_manual_slider(self.egress_frame, "Reaction Time (Mean)", "reaction_time_mean", 0.0, 10.0, initial=2.0)
        self.add_manual_slider(self.egress_frame, "Panic Level (0-1)", "panic_level", 0.0, 1.0, initial=0.5)

        # --- SECTION 5: FAA PASSENGER DEMOGRAPHICS ---
        demo_frame = ttk.Labelframe(self, text="FAA Appendix J Demographics", padding=10, bootstyle="warning")
        demo_frame.pack(fill=X, pady=5)
        
        # Female % slider with requirement indicator
        self.add_faa_slider(demo_frame, "Female %", "female_pct", 0, 100, 
                           requirement=40, req_text="FAA requires ≥40%")
        
        # Over 50 % slider with requirement indicator
        self.add_faa_slider(demo_frame, "Over 50 Years %", "over_50_pct", 0, 100, 
                           requirement=35, req_text="FAA requires ≥35%")
        
        # Female AND Over 50 calculated indicator
        self.overlap_frame = ttk.Frame(demo_frame)
        self.overlap_frame.pack(fill=X, pady=5)
        # Note: Simulation Engine now FORCES 15% overlap if female% and over50% allow it.
        self.overlap_lbl = ttk.Label(self.overlap_frame, text="Female + Over 50 (Req ≥15%):", width=35)
        self.overlap_lbl.pack(side=LEFT)
        self.overlap_status = ttk.Label(self.overlap_frame, text="✓ ENFORCED", foreground="green", font=("Helvetica", 9, "bold"))
        self.overlap_status.pack(side=RIGHT)
        
        # Simulated Infants
        infant_row = ttk.Frame(demo_frame)
        infant_row.pack(fill=X, pady=2)
        self.var_simulated_infants = tk.IntVar(value=3)
        ttk.Label(infant_row, text="Simulated Infants (dolls): ", width=25).pack(side=LEFT)
        ttk.Spinbox(infant_row, from_=0, to=10, textvariable=self.var_simulated_infants, width=5).pack(side=LEFT)
        ttk.Label(infant_row, text="  FAA requires 3", foreground="gray").pack(side=LEFT)
        
        
        # --- SECTION 5B: PASSENGER MIX ---
        mix_frame = ttk.Labelframe(self, text="Passenger Mix (%)", padding=10, bootstyle="info")
        mix_frame.pack(fill=X, pady=5)
        
        self.add_manual_slider(mix_frame, "Business %", "business_pct", 0, 100, is_mix=True)
        self.add_manual_slider(mix_frame, "Families %", "family_pct", 0, 100, is_mix=True)
        self.add_manual_slider(mix_frame, "PRM %", "prm_pct", 0, 100, is_mix=True)

        # --- SECTION 6: PHYSICS ---
        beh_frame = ttk.Labelframe(self, text="Physics", padding=10, bootstyle="secondary")
        beh_frame.pack(fill=X, pady=5)
        # Per-type speeds
        # Wider labels to ensure full text is visible
        label_w = 32
        self.add_manual_slider(beh_frame, "Speed - Business (m/s)", "speed_business", 0.5, 2.5, initial=self.base_config.behavior.speed_business, label_width=label_w)
        self.add_manual_slider(beh_frame, "Speed - Economy (m/s)", "speed_economy", 0.3, 2.5, initial=self.base_config.behavior.speed_economy, label_width=label_w)
        self.add_manual_slider(beh_frame, "Speed - Family (m/s)", "speed_family", 0.3, 2.5, initial=self.base_config.behavior.speed_family, label_width=label_w)
        self.add_manual_slider(beh_frame, "Speed - Wheelchair/PRM (m/s)", "speed_prm", 0.1, 2.0, initial=self.base_config.behavior.speed_prm, label_width=label_w)
        
        lf_frame = ttk.Labelframe(self, text="Occupancy", padding=10)
        lf_frame.pack(fill=X, pady=5)
        self.add_manual_slider(lf_frame, "Load Factor (%)", "load_factor", 50, 100, is_percentage=True)
        
        # --- FOOTER ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=X, pady=20)
        ttk.Button(btn_frame, text="EXIT APP", command=self.quit_app, bootstyle="danger-outline").pack(side=LEFT, ipadx=10)
        ttk.Button(btn_frame, text="START EVACUATION SIMULATION", command=self.on_run, bootstyle="danger").pack(side=RIGHT, fill=X, expand=True, padx=10)

    def quit_app(self):
        self.controller.destroy()
        sys.exit()

    # Removed toggle_mode_ui

    def refresh_door_checkboxes(self):
        for w in self.door_chk_frame.winfo_children(): w.destroy()
        self.door_vars = {}
        
        # Grid layout for checkboxes (2 columns)
        r, c = 0, 0
        for i, d in enumerate(self.base_config.lopa.door_locations):
            var = tk.BooleanVar(value=True)
            self.door_vars[d.name] = var
            cb = ttk.Checkbutton(self.door_chk_frame, text=d.name, variable=var, bootstyle="round-toggle")
            cb.grid(row=r, column=c, padx=5, pady=2, sticky=W)
            c += 1
            if c > 1:
                c = 0
                r += 1
        
    def reload_config(self, event):
        path = os.path.join(self.layouts_dir, self.lopa_var.get())
        try:
            self.base_config = SimConfig.from_json(path)
            # No door combo invalidation needed
            self.refresh_door_checkboxes() # Refresh Egress UI
                
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to load layout:\n{e}")

    def add_dropdown(self, parent, label, key, opts):
        val = getattr(self.base_config, key, opts[0])
        var = tk.StringVar(value=val)
        setattr(self, f"var_{key}", var)
        ttk.Label(parent, text=label).pack(anchor=W)
        ttk.Combobox(parent, textvariable=var, values=opts, state="readonly").pack(fill=X)

    def add_manual_slider(self, parent, label, key, min_v, max_v, is_mix=False, is_percentage=False, initial=None, label_width=25):
        if initial is None:
            if is_mix: initial = getattr(self.base_config.pax_mix, key)
            elif is_percentage: initial = self.base_config.load_factor * 100
            else: initial = getattr(self.base_config.behavior, key)
        var = tk.DoubleVar(value=initial)
        setattr(self, f"var_{key}", var)
        row = ttk.Frame(parent)
        row.pack(fill=X)
        lbl = ttk.Label(row, text=f"{label}: {initial:.1f}", width=label_width)
        lbl.pack(side=LEFT)
        def update(v): lbl.config(text=f"{label}: {float(v):.1f}")
        ttk.Scale(row, from_=min_v, to=max_v, variable=var, command=update).pack(side=RIGHT, fill=X, expand=True)

    def add_faa_slider(self, parent, label, key, min_v, max_v, requirement, req_text):
        """Add slider with FAA pass/fail indicator."""
        initial = getattr(self.base_config.pax_mix, key)
        var = tk.DoubleVar(value=initial)
        setattr(self, f"var_{key}", var)
        
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=2)
        
        lbl = ttk.Label(row, text=f"{label}: {initial:.0f}%", width=20)
        lbl.pack(side=LEFT)
        
        status_lbl = ttk.Label(row, text="✓ PASS" if initial >= requirement else "✗ FAIL", 
                               foreground="green" if initial >= requirement else "red",
                               font=("Helvetica", 9, "bold"), width=8)
        status_lbl.pack(side=RIGHT)
        
        req_lbl = ttk.Label(row, text=req_text, foreground="gray", font=("Helvetica", 8))
        req_lbl.pack(side=RIGHT, padx=5)
        
        def update(v):
            val = float(v)
            lbl.config(text=f"{label}: {val:.0f}%")
            if val >= requirement:
                status_lbl.config(text="✓ PASS", foreground="green")
            else:
                status_lbl.config(text="✗ FAIL", foreground="red")
            self.update_overlap_indicator()
        
        scale = ttk.Scale(row, from_=min_v, to=max_v, variable=var, command=update)
        scale.pack(side=LEFT, fill=X, expand=True, padx=5)

    def update_overlap_indicator(self):
        """Update overlap indicator text."""
        # Logic is now enforced in engine.py to 15% overlap
        # Check if user settings assume impossibility of 15% overlap (e.g. Total Female < 15%)
        female_pct = getattr(self, "var_female_pct", tk.DoubleVar(value=40)).get()
        over_50_pct = getattr(self, "var_over_50_pct", tk.DoubleVar(value=35)).get()
        
        possible = (female_pct >= 15) and (over_50_pct >= 15)
        
        if hasattr(self, 'overlap_status'):
             if possible:
                 self.overlap_status.config(text="✓ ENORCED (≥15%)", foreground="green")
             else:
                 self.overlap_status.config(text="✗ IMPOSSIBLE", foreground="red")

    def get_current_config(self):
        cfg = self.base_config 
        
        cfg.mode = "egress" # Forced

        # Egress Values
        cfg.behavior.visibility_factor = getattr(self, "var_visibility_factor").get()
        cfg.behavior.slide_delay_sec = getattr(self, "var_slide_delay_sec").get()
        cfg.behavior.reaction_time_mean = getattr(self, "var_reaction_time_mean").get()
        cfg.behavior.panic_level = getattr(self, "var_panic_level").get()
             
        # Populate active_exits dict
        for name, var in self.door_vars.items():
            cfg.behavior.active_exits[name] = var.get()

        # Boarding vars (Ignored, defaults)
        cfg.strategy = "realistic_random"
        cfg.primary_door = "L2"
        
        # Per-type speeds from UI
        cfg.behavior.speed_business = getattr(self, "var_speed_business").get()
        cfg.behavior.speed_economy = getattr(self, "var_speed_economy").get()
        cfg.behavior.speed_family = getattr(self, "var_speed_family").get()
        cfg.behavior.speed_prm = getattr(self, "var_speed_prm").get()
        if hasattr(self, "var_stow_time_mean"):
             cfg.behavior.stow_time_mean = getattr(self, "var_stow_time_mean").get()

        cfg.behavior.seat_shuffle_sec = getattr(self, "var_seat_shuffle_sec", tk.DoubleVar(value=20.0)).get()
        
        # FAA Appendix J Demographics
        cfg.pax_mix.female_pct = int(getattr(self, "var_female_pct").get())
        cfg.pax_mix.over_50_pct = int(getattr(self, "var_over_50_pct").get())
        cfg.pax_mix.simulated_infants = int(getattr(self, "var_simulated_infants").get())

        
        # Helper to safely get mix vars if they exist (handling potential race conditions with mix widgets)
        if hasattr(self, "var_business_pct"):
            cfg.pax_mix.business_pct = getattr(self, "var_business_pct").get()
            cfg.pax_mix.family_pct = getattr(self, "var_family_pct").get()
            cfg.pax_mix.prm_pct = getattr(self, "var_prm_pct").get()

        cfg.load_factor = getattr(self, "var_load_factor").get() / 100.0
        return cfg

    def on_run(self):
        cfg = self.get_current_config()
        self.notify_exit_requirement(cfg)
        self.controller.start_simulation(cfg)

    def notify_exit_requirement(self, cfg):
        """Notify user if door blocking meets FAA 50% exit availability."""
        total = len(cfg.lopa.door_locations)
        active = sum(1 for d in cfg.lopa.door_locations if cfg.behavior.active_exits.get(d.name, d.active))
        blocked = total - active
        # FAA BWB test: 3 or more doors must be blocked
        if blocked >= 3:
            tk.messagebox.showinfo("Exit Availability", f"PASS: {blocked}/{total} exits blocked (FAA BWB test requires ≥3 blocked)")
        else:
            tk.messagebox.showwarning("Exit Availability", f"FAIL: {blocked}/{total} exits blocked (need ≥3 blocked for FAA BWB test)")

if __name__ == "__main__":
    app = BWBApp()
    app.mainloop()