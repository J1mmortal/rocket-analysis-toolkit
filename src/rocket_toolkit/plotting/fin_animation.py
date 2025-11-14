import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
import os
import json

config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

def create_fin_temperature_animation(fin_tracker, output_path="fin_animation.mp4"):
    if not fin_tracker or not fin_tracker.time_points:
        print("No fin temperature data available for animation")
        return None

    print(f"Creating animation with {len(fin_tracker.time_points)} flight time points...")
    
    # Store the initial temperature field and fin conditions
    initial_temperature = fin_tracker.thermal_analyzer.current_temperature.copy()
    initial_altitude = fin_tracker.fin.altitude
    initial_velocity = fin_tracker.fin.velocity
    
    # Get fin dimensions and thermal properties
    height_m = fin_tracker.fin.fin_height / 1000
    width_m = fin_tracker.fin.fin_width / 1000
    material_name = fin_tracker.fin.material_name
    max_service_temp = fin_tracker.fin.max_service_temp
    
    # Create mask for delta fin shape
    X, Y = fin_tracker.thermal_analyzer.X, fin_tracker.thermal_analyzer.Y
    mask = np.zeros_like(initial_temperature, dtype=bool)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            y_val = Y[i, j]
            x_val = X[i, j]
            leading_edge_x = (y_val / height_m) * width_m
            if x_val < leading_edge_x:
                mask[i, j] = True
    
    # Select frames for animation (evenly spaced)
    num_frames = min(config.animation_frames, len(fin_tracker.time_points))
    frame_indices = np.linspace(0, len(fin_tracker.time_points)-1, num_frames, dtype=int)
    
    # Check if the tracker has absolute maximum temperature information
    has_absolute_max = (hasattr(fin_tracker, 'absolute_max_temperature') and 
                       fin_tracker.absolute_max_temperature is not None)
    
    # Get the maximum temperature field if available
    max_temp_field = None
    global_max_temp = 0
    
    if hasattr(fin_tracker.thermal_analyzer, 'max_temperature_reached'):
        max_temp_field = fin_tracker.thermal_analyzer.max_temperature_reached.copy()
        masked_max_temp = np.ma.array(max_temp_field, mask=mask)
        global_max_temp = np.max(masked_max_temp)
        print(f"Maximum temperature field available with peak: {global_max_temp:.2f}K")
    
    # If the global max wasn't already reported elsewhere, use it here
    if has_absolute_max:
        abs_max = fin_tracker.absolute_max_temperature
        if abs_max > global_max_temp:
            global_max_temp = abs_max
        print(f"Using absolute maximum temperature: {global_max_temp:.2f}K")
        if hasattr(fin_tracker, 'absolute_max_temperature_info'):
            max_info = fin_tracker.absolute_max_temperature_info
            print(f"Occurred at time: {max_info['time']:.2f}s, Mach: {max_info['mach']:.2f}")
    
    # Access previously calculated temperature frames directly if available
    temperature_frames = []
    frame_max_temps = []
    stored_frames = []
    
    if hasattr(fin_tracker.thermal_analyzer, 'get_temperature_frames'):
        stored_frames = fin_tracker.thermal_analyzer.get_temperature_frames()
    
    if stored_frames:
        print(f"Using {len(stored_frames)} pre-calculated temperature frames")
        # Sample evenly from the stored frames
        if len(stored_frames) >= num_frames:
            indices = np.linspace(0, len(stored_frames)-1, num_frames, dtype=int)
            for idx in indices:
                frame_data = stored_frames[idx]
                temperature_frames.append(frame_data["temperature"].copy())
                frame_max_temps.append(frame_data["max_temp"])
        else:
            # Just use all frames if we don't have enough
            for frame_data in stored_frames:
                temperature_frames.append(frame_data["temperature"].copy())
                frame_max_temps.append(frame_data["max_temp"])
    else:
        # If we don't have stored frames, need to ensure consistency with other calculations
        print("Pre-calculating temperature fields for animation...")
        
        # Reset to original state
        fin_tracker.fin.altitude = initial_altitude
        fin_tracker.fin.velocity = initial_velocity
        
        # Use the main flight history data to calculate temperatures at each frame
        for frame_idx, idx in enumerate(frame_indices):
            altitude = fin_tracker.altitude_history[idx]
            velocity = fin_tracker.velocity_history[idx]
            time = fin_tracker.time_points[idx]
            
            # Set flight conditions
            fin_tracker.fin.altitude = altitude
            fin_tracker.fin.velocity = velocity
            
            # Get temperature field from main history (if available)
            if idx < len(fin_tracker.max_temp_history):
                # Use the temperature from thermal_analyzer at this point if possible
                atm_props = fin_tracker.thermal_analyzer.atm_model.get_atmosphere_properties(altitude)
                air_temp = atm_props["temperature"]
                
                # For critical points, use the actual max temperature field to ensure consistency
                if max_temp_field is not None and has_absolute_max and hasattr(fin_tracker, 'absolute_max_temperature_info'):
                    max_time = fin_tracker.absolute_max_temperature_info["time"]
                    if abs(time - max_time) < 0.2:  # If very close to max temperature time
                        temperature_field = max_temp_field.copy()
                        max_temp = global_max_temp
                    else:
                        # Otherwise use the actual recorded temperature
                        max_temp = fin_tracker.max_temp_history[idx]
                        
                        # Create a temperature field with this max
                        if frame_idx == 0:
                            temperature_field = np.ones_like(initial_temperature) * air_temp
                        else:
                            temperature_field = temperature_frames[-1].copy()
                        
                        # Scale to match the recorded maximum
                        current_max = np.max(np.ma.array(temperature_field, mask=mask))
                        if current_max > air_temp:
                            # Scale all temperatures above ambient
                            scale_factor = (max_temp - air_temp) / (current_max - air_temp)
                            temperature_field = air_temp + (temperature_field - air_temp) * scale_factor
                        else:
                            # Just set the maximum point
                            max_idx = np.unravel_index(np.argmax(np.ma.array(temperature_field, mask=mask)), temperature_field.shape)
                            temperature_field[max_idx] = max_temp
                else:
                    # Use the temperature from history if available
                    max_temp = fin_tracker.max_temp_history[idx]
                    
                    # Create a temperature field with this max
                    if frame_idx == 0:
                        temperature_field = np.ones_like(initial_temperature) * air_temp
                    else:
                        temperature_field = temperature_frames[-1].copy()
                    
                    # Scale to match the recorded maximum
                    current_max = np.max(np.ma.array(temperature_field, mask=mask))
                    if current_max > air_temp:
                        # Scale all temperatures above ambient
                        scale_factor = (max_temp - air_temp) / (current_max - air_temp)
                        temperature_field = air_temp + (temperature_field - air_temp) * scale_factor
                    else:
                        # Just set the maximum point
                        max_idx = np.unravel_index(np.argmax(np.ma.array(temperature_field, mask=mask)), temperature_field.shape)
                        temperature_field[max_idx] = max_temp
            else:
                # If we don't have history data, use a simple model
                atm_props = fin_tracker.thermal_analyzer.atm_model.get_atmosphere_properties(altitude)
                air_temp = atm_props["temperature"]
                temperature_field = np.ones_like(initial_temperature) * air_temp
                max_temp = air_temp
            
            # Store the temperature field
            temperature_frames.append(temperature_field)
            frame_max_temps.append(max_temp)
            
            # Print debug info for every few frames
            if frame_idx % max(1, num_frames//5) == 0:
                print(f"Frame {frame_idx}/{num_frames}: Time {time:.2f}s, "
                      f"Max temp: {max_temp:.2f}K, Air temp: {air_temp:.2f}K")
    
    # Find the overall maximum temperature across all frames
    overall_max_temp = max(frame_max_temps) if frame_max_temps else global_max_temp
    
    # Make sure we're using the absolute maximum temp from any source
    if has_absolute_max and fin_tracker.absolute_max_temperature > overall_max_temp:
        overall_max_temp = fin_tracker.absolute_max_temperature
        print(f"Using absolute maximum temperature: {overall_max_temp:.2f}K")
    else:
        print(f"Maximum temperature in animation frames: {overall_max_temp:.2f}K")
    
    # Restore original state
    fin_tracker.fin.altitude = initial_altitude
    fin_tracker.fin.velocity = initial_velocity
    
    print(f"Generated {len(temperature_frames)} temperature frames for animation")
    
    # Create a list to store each frame for the animation
    print("Creating frames for animation...")
    frames = []
    
    # Set up color map
    colors = [(0, 'blue'), (0.5, 'yellow'), (1, 'red')]
    cmap = LinearSegmentedColormap.from_list('thermal', colors)
    
    # Draw the fin outline - we'll keep this fixed throughout animation
    # Leading edge curve
    leading_edge_x = []
    leading_edge_y = []
    for y_pos in np.linspace(0, height_m, 50):
        x_pos = (y_pos / height_m) * width_m
        leading_edge_x.append(x_pos)
        leading_edge_y.append(y_pos)
    
    # IMPORTANT: Set fixed figure size with even pixel dimensions for FFmpeg
    # Using figsize=(8, 8) will ensure dimensions are divisible by 2
    fig_width = 8  # inches
    fig_height = 8  # inches
    dpi = 100
    
    # Calculate reasonable temperature scale based on max temperature
    temp_min = 200  # K (well below ambient)
    temp_max = max(300, overall_max_temp + 20)  # At least 1000K or slightly above max
    
    for frame_idx in range(len(temperature_frames)):
        # Create a figure with dimensions divisible by 2
        fig_frame = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
        ax_frame = fig_frame.add_subplot(1, 1, 1)
        
        # Get the corresponding time point and data
        idx = frame_indices[frame_idx]
        current_time = fin_tracker.time_points[idx]
        current_mach = fin_tracker.mach_history[idx]
        temperature = temperature_frames[frame_idx]
        masked_temp = np.ma.array(temperature, mask=mask)
        
        # Create a copy for visualization that's clipped to reasonable values
        display_temp = np.clip(masked_temp, temp_min, temp_max)
        
        # Check if there are any extreme values that were clipped
        if np.min(masked_temp) < temp_min or np.max(masked_temp) > temp_max:
            print(f"WARNING: Frame {frame_idx} had extreme temperatures: "
                  f"Min: {np.min(masked_temp):.2f}K, Max: {np.max(masked_temp):.2f}K - "
                  f"These have been clipped for visualization.")
        
        # Create the contour plot for this frame using the clipped values
        contour = ax_frame.contourf(X, Y, display_temp, cmap=cmap, levels=20, vmin=temp_min, vmax=temp_max)
        
        # Add fin outline for this frame
        ax_frame.plot(leading_edge_x, leading_edge_y, 'k-', linewidth=2)  # Leading edge
        ax_frame.plot([width_m, width_m], [0, height_m], 'k-', linewidth=2)  # Trailing edge
        ax_frame.plot([0, width_m], [0, 0], 'k-', linewidth=2)  # Bottom edge
        ax_frame.plot([leading_edge_x[-1], width_m], [height_m, height_m], 'k-', linewidth=2)  # Top edge
        
        # Add annotations
        ax_frame.text(width_m/2, -0.005, "Fuselage side", ha='center', fontsize=12)
        ax_frame.text(width_m + 0.003, height_m/2, "Free end", ha='left', va='center', fontsize=12, rotation=90)
        
        # Add airflow arrow
        arrow_y = height_m/2
        ax_frame.arrow(-0.005, arrow_y, 0.005, 0, head_width=0.004, head_length=0.002, 
                 fc='black', ec='black', width=0.001)
        ax_frame.text(0, arrow_y + 0.005, "Airflow", ha='right', fontsize=10)
        
        # Add colorbar
        cbar = fig_frame.colorbar(contour, ax=ax_frame)
        cbar.set_label('Temperature (K)')
        
        # Add title - include maximum temperature reference and fixed consistent max
        frame_max_temp = np.max(masked_temp)
        
        if has_absolute_max and abs(frame_max_temp - overall_max_temp) > 0.1:
            title = (f'Temperature Distribution at t={current_time:.1f}s, Mach={current_mach:.2f}\n'
                    f'Frame Max: {frame_max_temp:.1f}K, Global Max: {overall_max_temp:.1f}K')
        else:
            title = f'Temperature Distribution at t={current_time:.1f}s, Mach={current_mach:.2f}'
            
        if np.min(masked_temp) < temp_min or np.max(masked_temp) > temp_max:
            title += f' (Clipped: {np.min(masked_temp):.0f}-{np.max(masked_temp):.0f}K)'
        
        ax_frame.set_title(title)
        
        # Add hotspot marker
        max_temp_idx = np.unravel_index(np.argmax(display_temp), display_temp.shape)
        hottest_x = X[max_temp_idx]
        hottest_y = Y[max_temp_idx]
        ax_frame.plot(hottest_x, hottest_y, 'ro', markersize=8)
        
        # Add label with current max and global max if different
        if has_absolute_max and abs(frame_max_temp - overall_max_temp) > 0.1:
            ax_frame.text(hottest_x, hottest_y + height_m * 0.05, 
                      f"Current max: {frame_max_temp:.1f}K\nGlobal max: {overall_max_temp:.1f}K", 
                      ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        else:
            ax_frame.text(hottest_x, hottest_y + height_m * 0.05, f"Max: {frame_max_temp:.1f}K", 
                       ha='center', fontsize=10, bbox=dict(facecolor='white', alpha=0.7))
        
        # Add info text
        info_str = f'Flight Conditions:\n'
        info_str += f'  Time: {current_time:.1f} s\n'
        info_str += f'  Velocity: {fin_tracker.velocity_history[idx]:.1f} m/s\n'
        info_str += f'  Altitude: {fin_tracker.altitude_history[idx]:.1f} m\n'
        info_str += f'  Mach: {current_mach:.2f}\n\n'
        info_str += f'Material: {material_name}\n'
        info_str += f'  Max Service Temp: {max_service_temp} K\n'
        
        # Reference global maximum for safety margin calculation
        margin = max_service_temp - overall_max_temp
        info_str += f'  Peak Fin Temp: {overall_max_temp:.1f}K\n'
        info_str += f'  Safety Margin: {margin:.1f} K'
        
        # Add warning if margin is negative
        if margin < 0:
            info_str += f' (EXCEEDS LIMIT by {abs(margin):.1f}K)'
            
        plt.figtext(0.5, 0.01, info_str, ha='center', 
                   bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
        
        # Add temperature limit indicators if needed
        if max_service_temp < temp_max:
            # Add a line showing the temperature limit
            ax_frame.contour(X, Y, display_temp, levels=[max_service_temp], 
                          colors='red', linestyles='dashed', linewidths=2)
            
            # Add text label for the limit
            ax_frame.text(width_m/2, height_m*0.8, f"Service Limit: {max_service_temp}K", 
                       ha='center', color='red', fontsize=10, fontweight='bold',
                       bbox=dict(facecolor='white', alpha=0.7))
            
            # Highlight areas above temperature limit
            if np.max(display_temp) > max_service_temp:
                over_temp = np.ma.masked_where((display_temp <= max_service_temp) | mask, display_temp)
                ax_frame.contourf(X, Y, over_temp, colors='red', alpha=0.3, 
                             levels=[max_service_temp, temp_max])
        
        # Set up axes
        ax_frame.set_xlabel('Width (m) - Chord Direction')
        ax_frame.set_ylabel('Height (m) - Span Direction')
        ax_frame.set_xlim(-0.01, width_m + 0.01)
        ax_frame.set_ylim(-0.01, height_m + 0.01)
        ax_frame.set_aspect('equal')
        
        # Adjust layout
        plt.tight_layout()
        
        # Create frames directory if it doesn't exist
        frame_dir = "temp_frames"
        os.makedirs(frame_dir, exist_ok=True)
        
        # Save the figure to a file - ensure it has even dimensions
        frame_path = os.path.join(frame_dir, f"frame_{frame_idx:03d}.png")
        plt.savefig(frame_path, dpi=dpi, bbox_inches=None)  # Don't use bbox_inches to maintain even dimensions
        frames.append(frame_path)
        
        # Close the figure to free memory
        plt.close(fig_frame)
    
    print(f"Created {len(frames)} frames. Combining into animation...")
    
    # Now create the animation from the saved frames
    try:
        # Try using FFmpeg directly
        import subprocess
        
        # Check if output directory exists, create if not
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Force the frame size to be even (required for h264)
        # Create a temporary script to force dimensions
        resize_script = """
        @echo off
        mkdir resized_frames
        for %%i in (temp_frames\\frame_*.png) do (
            ffmpeg -y -i "%%i" -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "resized_frames\\%%~nxi"
        )
        """
        
        with open("resize_frames.bat", "w") as f:
            f.write(resize_script)
        
        # Run the resize script
        subprocess.run(["resize_frames.bat"], shell=True, check=True)
        
        # Build FFmpeg command using the resized frames
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-framerate', '5',  # Frame rate
            '-i', 'resized_frames/frame_%03d.png',  # Input pattern
            '-c:v', 'libx264',  # Codec
            '-pix_fmt', 'yuv420p',  # Pixel format
            '-crf', '23',  # Quality
            output_path  # Output file
        ]
        
        # Run FFmpeg
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode == 0:
            print(f"Animation successfully saved to {output_path}")
        else:
            print("Error creating animation with FFmpeg:", result.stderr.decode())
            # Fall back to creating a GIF with PIL
            raise Exception("FFmpeg failed")
    
    except Exception as e:
        print(f"FFmpeg error: {e}")
        print("Trying to create GIF using PIL instead...")
        
        try:
            from PIL import Image
            
            # Create GIF with PIL
            gif_path = output_path.replace('.mp4', '.gif')
            images = []
            
            for frame_path in frames:
                images.append(Image.open(frame_path))
            
            # Save as GIF
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                optimize=False,
                duration=200,  # 200ms per frame = 5fps
                loop=0  # Loop forever
            )
            
            print(f"Animation saved as GIF to {gif_path}")
            output_path = gif_path
        
        except Exception as e2:
            print(f"GIF creation failed: {e2}")
            print("Animation could not be saved.")
    
    # Clean up temporary frame files
    try:
        print("Cleaning up temporary files...")
        for frame_path in frames:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        
        # Also clean up resized frames if they exist
        resized_dir = "resized_frames"
        if os.path.exists(resized_dir):
            for filename in os.listdir(resized_dir):
                file_path = os.path.join(resized_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(resized_dir)
        
        # Remove temp folders
        if os.path.exists(frame_dir) and len(os.listdir(frame_dir)) == 0:
            os.rmdir(frame_dir)
        
        # Remove resize script
        if os.path.exists("resize_frames.bat"):
            os.remove("resize_frames.bat")
    except Exception as e:
        print(f"Warning: Could not clean up some temp files: {e}")
    
    # Update the fin_tracker's absolute maximum temperature from what we found
    if not has_absolute_max and overall_max_temp > 0:
        if hasattr(fin_tracker, 'absolute_max_temperature'):
            fin_tracker.absolute_max_temperature = overall_max_temp
    
    return output_path