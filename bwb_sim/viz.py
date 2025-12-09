# bwb_sim/viz.py
import matplotlib.pyplot as plt
import imageio.v2 as imageio
import numpy as np
import os
from tqdm import tqdm

def create_animation(sim, save_path):
    print("Processing animation frames...")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    images = []
    lopa = sim.cfg.lopa
    
    # SPEED OPTIMIZATION: Only render every 5th frame
    frames_to_render = sim.snapshots[::5] 
    
    # Setup Figure
    fig, ax = plt.subplots(figsize=(8, 10))
    
    for frame_idx, agents in enumerate(tqdm(frames_to_render, unit="frame")):
        ax.clear()
        ax.set_title(f"BWB Boarding - Time: {frame_idx*2.5:.1f}s")
        ax.invert_yaxis()
        
        # Draw Map
        for section in lopa.sections:
            layout = section.layout_string
            for r in range(section.start_row, section.end_row + 1):
                for c, char in enumerate(layout):
                    if char == '|':
                        ax.plot([c-0.5, c-0.5], [r-0.5, r+0.5], 'k-', lw=2)
                    elif char == 'S':
                        ax.plot(c, r, 's', color='lightgray', ms=5)
        
        # Draw Agents
        if agents:
            rs = [a['r'] for a in agents]
            cs = [a['c'] for a in agents]
            ax.plot(cs, rs, 'bo', ms=8)
            
        # Capture
        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.buffer_rgba(), dtype='uint8')
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (4,))
        images.append(image[:, :, :3]) # Keep RGB
    
    print("Saving GIF file...")
    imageio.mimsave(save_path, images, fps=10)
    plt.close()
    print(f"Animation saved to {save_path}")