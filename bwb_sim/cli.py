# FILE: bwb_sim/cli.py
import typer
import os
from .config import SimConfig
from .engine import Simulation
from .viz import create_animation

app = typer.Typer()

@app.command()
def run(
    layout: str = "layouts/bwb_4bay.json", 
    door: str = None, 
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch the simulation live")
):
    """Run the simulation."""
    
    if not os.path.exists(layout):
        print(f"Error: Layout file '{layout}' not found.")
        raise typer.Exit(code=1)

    cfg = SimConfig.from_json(layout)
    if door:
        cfg.primary_door = door
        
    print(f"Loading {cfg.lopa.name} via Door {cfg.primary_door}...")
    
    sim = Simulation(cfg)
    
    if watch:
        # Import here to avoid circular imports or GUI issues in headless environments
        from .live_viz import run_live_standalone
        print("Note: For the full UI experience, please run 'launcher.py' instead.")
        # This function doesn't exist in the new class-based system, 
        # so we encourage using launcher.py
    else:
        # Run Fast & Save GIF
        sim.run()
        output_file = f"{cfg.save_dir}/simulation.gif"
        create_animation(sim, output_file)

if __name__ == "__main__":
    app()