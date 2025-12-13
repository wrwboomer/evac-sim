# FILE: bwb_sim/live_viz.py
import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import numpy as np
from .reports import get_report_string
import sys
import os
import traceback

class LiveSimulationFrame(ttk.Frame):
    def __init__(self, parent, sim, on_new_sim_callback):
        super().__init__(parent)
        self.sim = sim
        self.on_new_sim = on_new_sim_callback 
        self.is_running = False
        self.show_heatmap = False
        self.sim_speed_factor = 10.0 
        self.step_size = 0.5 
        self.current_time = 0
        self.after_id = None
        self.scale_x = 0.5
        self.scale_y = 0.8
        
        self.max_row = max(1, self.sim.cfg.lopa.rows_total)
        self.max_col = 0
        for section in self.sim.cfg.lopa.sections:
            if len(section.layout_string) > self.max_col:
                self.max_col = len(section.layout_string)
        
        # --- CRITICAL LOGIC ---
        # If this block fails, the screen is blank.
        try:
            if self.sim.cfg.mode == "egress":
                self.sim._generate_passengers_seated()
                
                # --- PRE-COMPUTE BFS MAPS (Critical for GUI Mode) ---
                print("GUI: Computing Pathfinding Maps...")
                self.sim.door_maps = {}
                # Apply UI Overrides
                override = self.sim.cfg.behavior.active_exits
                active_doors = []
                for d in self.sim.cfg.lopa.door_locations:
                    is_active = override.get(d.name, d.active)
                    if is_active:
                        active_doors.append(d)

                if not active_doors: active_doors = self.sim.cfg.lopa.door_locations
                
                # Initialize door resources (capacity=1) for FIFO exit flow
                # CRITICAL: This was missing, causing door physics to fail
                import simpy
                for d in active_doors:
                    self.sim.door_resources[d.name] = simpy.Resource(self.sim.env, capacity=1)
                    # Door node is target. Using list [(r,c)] as expected by geometry
                    self.sim.door_maps[d.name] = self.sim.geo.compute_distance_map([(d.row, d.col)])
                
                self.sim.env.process(self.sim.evacuation_control(active_doors))
            else:
                self.sim._generate_passengers()
                self.sim.env.process(self.sim.boarding_control())
                
            self.sim.env.process(self.sim.snapshot_loop())
            
            self.setup_ui()
            self.setup_plot()
            self.bind("<Destroy>", self.cleanup)
            self.draw_frame() # Initial Draw
            self.is_running = True
            self.animate_step()
        except Exception as e:
            print(traceback.format_exc())

    def setup_ui(self):
        header_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        header_frame.pack(side=TOP, fill=X)
        ac_name = self.sim.cfg.lopa.name
        mode_text = "BOARDING" if self.sim.cfg.mode != "egress" else "EVACUATION"
        style = "primary" if self.sim.cfg.mode != "egress" else "danger"
        ttk.Label(header_frame, text=f"{mode_text}: {ac_name}", font=("Helvetica", 16, "bold"), bootstyle=style).pack(anchor=CENTER)
        ttk.Separator(header_frame, orient=HORIZONTAL).pack(fill=X, pady=5)

        control_panel = ttk.Frame(self, padding=10)
        control_panel.pack(side=BOTTOM, fill=X)
        
        speed_frame = ttk.Frame(control_panel)
        speed_frame.pack(side=TOP, fill=X, pady=(0, 10))
        ttk.Label(speed_frame, text="Playback Speed:", font=("Helvetica", 10, "bold")).pack(side=LEFT)
        self.speed_scale = ttk.Scale(speed_frame, from_=1, to=100, value=10, command=self.update_speed)
        self.speed_scale.pack(side=LEFT, fill=X, expand=True, padx=10)
        self.speed_lbl = ttk.Label(speed_frame, text="10x", width=4)
        self.speed_lbl.pack(side=LEFT)

        btn_row = ttk.Frame(control_panel)
        btn_row.pack(side=BOTTOM, fill=X)
        self.btn_stop = ttk.Button(btn_row, text="PAUSE", command=self.toggle_pause, bootstyle="warning")
        self.btn_stop.pack(side=LEFT, padx=5, fill=X, expand=True)
        self.btn_heat = ttk.Button(btn_row, text="HEATMAP", command=self.toggle_heatmap, bootstyle="info-outline")
        self.btn_heat.pack(side=LEFT, padx=5, fill=X, expand=True)
        btn_report = ttk.Button(btn_row, text="REPORT", command=self.show_report_dialog, bootstyle="info")
        btn_report.pack(side=LEFT, padx=5, fill=X, expand=True)
        btn_new = ttk.Button(btn_row, text="NEW SIM", command=self.return_to_config, bootstyle="success")
        btn_new.pack(side=LEFT, padx=5, fill=X, expand=True)
        ttk.Separator(btn_row, orient=VERTICAL).pack(side=LEFT, padx=15, fill=Y)
        btn_exit = ttk.Button(btn_row, text="EXIT APP", command=self.quit_app, bootstyle="danger")
        btn_exit.pack(side=LEFT, padx=5, fill=X, expand=True)

    def update_speed(self, value):
        val = float(value)
        self.sim_speed_factor = val
        self.speed_lbl.config(text=f"{int(val)}x")

    def setup_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(6, 8))
        self.fig.patch.set_facecolor('#ffffff')
        self.fig.subplots_adjust(left=0.05, right=0.75, top=0.95, bottom=0.05)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=True)

    def cleanup(self, event=None):
        self.is_running = False
        if self.after_id:
            try: self.after_cancel(self.after_id)
            except: pass
            self.after_id = None

    def toggle_pause(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.btn_stop.config(text="PAUSE", bootstyle="warning")
            self.animate_step()
        else:
            self.btn_stop.config(text="RESUME", bootstyle="primary")
            if self.after_id: self.after_cancel(self.after_id); self.after_id = None

    def toggle_heatmap(self):
        self.show_heatmap = not self.show_heatmap
        if self.show_heatmap:
            self.btn_heat.config(bootstyle="info", text="HIDE MAP")
        else:
            self.btn_heat.config(bootstyle="info-outline", text="HEATMAP")
        if not self.is_running: self.draw_frame()

    def return_to_config(self):
        self.cleanup()
        self.on_new_sim()

    def quit_app(self):
        self.cleanup()
        self.winfo_toplevel().destroy()
        sys.exit()

    def show_report_dialog(self):
        was_running = self.is_running
        if self.is_running: self.toggle_pause()
        report_text = get_report_string(self.sim)
        top = ttk.Toplevel(self)
        top.title("Report")
        top.geometry("600x650")
        text_area = tk.Text(top, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        text_area.pack(expand=True, fill="both", padx=10, pady=10)
        text_area.insert("1.0", report_text)
        text_area.config(state="disabled") 
        def save():
            fp = filedialog.asksaveasfilename(defaultextension=".txt")
            if fp:
                with open(fp, "w") as f: f.write(report_text)
                tk.messagebox.showinfo("Success", "Saved.")
        def print_report():
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
                with os.fdopen(fd, 'w') as tmp: tmp.write(report_text)
                if sys.platform == "win32": os.startfile(temp_path, "print")
                else: import subprocess; subprocess.run(["lpr", temp_path])
                tk.messagebox.showinfo("Printing", "Sent to default printer.")
            except Exception as e:
                tk.messagebox.showerror("Print Error", str(e))
        btn_frame = ttk.Frame(top, padding=10)
        btn_frame.pack(fill=X, side=BOTTOM)
        ttk.Button(btn_frame, text="CLOSE", command=top.destroy).pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="SAVE AS...", command=save, bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="PRINT", command=print_report, bootstyle="info").pack(side=LEFT, padx=5)

    def animate_step(self):
        if not self.is_running: return
        try:
            if not self.winfo_exists(): self.is_running = False; return
        except Exception: return

        steps_per_frame = 1
        if self.sim_speed_factor > 5.0:
            steps_per_frame = int(self.sim_speed_factor / 4)
            if steps_per_frame < 1: steps_per_frame = 1

        try:
            for _ in range(steps_per_frame):
                self.sim.env.run(until=self.current_time + self.step_size)
                self.current_time += self.step_size
                
                done = False
                if self.sim.cfg.mode == "egress":
                    evac = len([p for p in self.sim.passengers if p.curr_r == -999])
                    if evac == len(self.sim.passengers): done = True
                else:
                    seat = len([p for p in self.sim.passengers if p.curr_r == -99])
                    if seat == len(self.sim.passengers): done = True
                if done:
                    self.is_running = False
                    self.draw_frame()
                    tk.messagebox.showinfo("Finished", f"Process Complete!\nTime: {self.format_time()}")
                    return
            self.draw_frame()
            self.after_id = self.after(30, self.animate_step)
        except Exception as e:
            print(traceback.format_exc())

    def get_phys_coords(self, r, c):
        return (c * self.scale_x, r * self.scale_y)

    def draw_frame(self):
        self.ax.clear()
        max_phys_x = (self.max_col) * self.scale_x
        max_phys_y = (self.max_row) * self.scale_y
        self.ax.set_xlim(-1, max_phys_x + 1)
        self.ax.set_ylim(-1, max_phys_y + 1)
        self.ax.set_aspect('equal')
        self.ax.invert_yaxis()
        self.ax.axis('off')

        if self.show_heatmap:
            self.ax.set_title(f"Time: {self.format_time()} | HEATMAP (Red=Congestion)")
            lopa = self.sim.cfg.lopa
            for section in lopa.sections:
                layout = section.layout_string
                for r in range(section.start_row, section.end_row + 1):
                    py = r * self.scale_y
                    for c, char in enumerate(layout):
                        px = c * self.scale_x
                        if char == '|': self.ax.plot([px, px], [py-0.4, py+0.4], color='#333333', lw=3, zorder=2)

            if self.sim.heatmap_accum:
                vals = list(self.sim.heatmap_accum.values())
                max_val = np.percentile(vals, 90) if vals else 1
                if max_val < 1: max_val = 1
                cmap = cm.get_cmap('turbo')
                for (r, c), count in self.sim.heatmap_accum.items():
                    # Only show heatmap for aisleways, not seats
                    cell_type = self.sim.geo.layout_map.get((r, c), '.')
                    if cell_type != '-':
                        continue  # Skip non-aisle cells
                    if count > 0:
                        norm = min(1.0, count / max_val)
                        rgba = cmap(norm)
                        px, py = self.get_phys_coords(r, c)
                        rect = mpatches.Rectangle((px-0.25, py-0.4), 0.5, 0.8, color=rgba, alpha=0.85, zorder=0)
                        self.ax.add_patch(rect)
            self.canvas.draw()
            return
        




        total_pax = len(self.sim.passengers) if self.sim.passengers else 1
        female_cnt = sum(1 for p in self.sim.passengers if getattr(p, "is_female", False))
        over50_cnt = sum(1 for p in self.sim.passengers if getattr(p, "is_over_50", False))
        infants_cnt = getattr(self.sim.cfg.pax_mix, "simulated_infants", 0)
        female_pct = (female_cnt / total_pax) * 100
        over50_pct = (over50_cnt / total_pax) * 100

        legend_patches = [
            mpatches.Patch(color='#9c27b0', label=f"Female > 50: {self.get_demo_count('both')}"),
            mpatches.Patch(color='#e91e63', label=f"Female < 50: {self.get_demo_count('female')}"),
            mpatches.Patch(color='#f39c12', label=f"Male > 50:   {self.get_demo_count('over50')}"),
            mpatches.Patch(color='#007acc', label="Male < 50"),
            mpatches.Patch(color='#666666', alpha=0.0, label=f"Infants: {infants_cnt}")
        ]
        self.ax.legend(handles=legend_patches, loc='upper left', bbox_to_anchor=(1.02, 1.0), ncol=1, fontsize=9, frameon=False)

        active = [p for p in self.sim.passengers if p.curr_r >= 0]
        seated = [p for p in self.sim.passengers if p.curr_r == -99]
        
        status = "Evacuating" if self.sim.cfg.mode == "egress" else "Seated"
        count = len(active) if self.sim.cfg.mode == "egress" else len(seated)
        self.ax.set_title(f"Time: {self.format_time()} | {status}: {count}/{len(self.sim.passengers)}")

        lopa = self.sim.cfg.lopa
        for section in lopa.sections:
            layout = section.layout_string
            for r in range(section.start_row, section.end_row + 1):
                py = r * self.scale_y
                for c, char in enumerate(layout):
                    px = c * self.scale_x
                    if char == '|': self.ax.plot([px, px], [py-0.4, py+0.4], color='#333333', lw=3)
                    elif char == '-':
                        rect = mpatches.Rectangle((px-0.25, py-0.4), 0.5, 0.8, color='#f0f8ff', zorder=0)
                        self.ax.add_patch(rect)
                    elif char == 'S': 
                        rect = mpatches.Rectangle((px-0.22, py-0.35), 0.44, 0.7, facecolor='white', edgecolor='#cccccc', lw=1, zorder=1)
                        self.ax.add_patch(rect)

        if seated:
            for p in seated:
                px, py = self.get_phys_coords(p.row, p.col)
                rect = mpatches.Rectangle((px-0.22, py-0.35), 0.44, 0.7, facecolor='#d9534f', edgecolor='#a94442', zorder=2)
                self.ax.add_patch(rect)

        # Draw blocked doors
        active_exits = self.sim.cfg.behavior.active_exits
        for door in self.sim.cfg.lopa.door_locations:
            is_active = active_exits.get(door.name, door.active)
            if not is_active:
                px, py = self.get_phys_coords(door.row, door.col)
                self.ax.plot(px, py, 'x', color='red', markersize=15, markeredgewidth=3, zorder=20)
            # Label doors (always show)
            px, py = self.get_phys_coords(door.row, door.col)
            # Place labels above for forward/mid, below for aft doors (higher row index)
            if door.row >= self.sim.cfg.lopa.rows_total - 1:
                self.ax.text(px, py + 0.8, door.name, fontsize=8, ha='center', va='top', color='#333333', zorder=21)
            else:
                self.ax.text(px, py - 0.6, door.name, fontsize=8, ha='center', va='bottom', color='#333333', zorder=21)

        for p in active:
            # Demographic-based coloring
            is_fem = getattr(p, "is_female", False)
            is_o50 = getattr(p, "is_over_50", False)
            
            if is_fem and is_o50:
                color = '#9c27b0' # Purple (Overlap)
            elif is_o50:
                color = '#f39c12' # Orange
            elif is_fem:
                color = '#e91e63' # Pink
            else:
                color = '#007acc' # Blue
            px, py = self.get_phys_coords(p.curr_r, p.curr_c)
            self.ax.plot(px, py, 'o', color=color, ms=6, markeredgecolor='white', zorder=10)

        self.canvas.draw()

    def get_demo_count(self, mode):
        # Helper for counting disjoint groups for visualization
        cnt = 0
        for p in self.sim.passengers:
            is_fem = getattr(p, "is_female", False)
            is_o50 = getattr(p, "is_over_50", False)
            if mode == 'both' and is_fem and is_o50: cnt += 1
            elif mode == 'female' and is_fem and not is_o50: cnt += 1
            elif mode == 'over50' and not is_fem and is_o50: cnt += 1
        return cnt

    def format_time(self):
        mins = int(self.current_time // 60)
        secs = int(self.current_time % 60)
        return f"{mins:02d}:{secs:02d}"