import tkinter as tk
from tkinter import ttk, filedialog
from transparent_background import *
import os
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import time


def browse_source_path():
    file_path = filedialog.askopenfilename(filetypes=[("Image and Video Files", "*.jpg;*.png;*.mp4;*.avi;*.mov")])
    source_entry.delete(0, tk.END)
    source_entry.insert(0, file_path)

def browse_destination_folder():
    folder_path = filedialog.askdirectory()
    destination_entry.delete(0, tk.END)
    destination_entry.insert(0, folder_path)

def set_default_ckpt_file():
    # Get the current directory where the Python script is located
    current_directory = os.path.dirname(os.path.abspath(__file__))
    ckpt_folder = os.path.join(current_directory, "ckpt")
    
    # Get a list of all .pth files in the ckpt folder
    pth_files = [file for file in os.listdir(ckpt_folder) if file.endswith('.pth')]
    
    # If there is at least one .pth file, set the first one as the default value
    if pth_files:
        default_ckpt_file = os.path.join(ckpt_folder, pth_files[0])
        ckpt_entry_var.set(default_ckpt_file)

# CKPT File Menu Functions
def on_file_open():
    ckpt_file = filedialog.askopenfilename(initialdir="./ckpt", filetypes=[("Checkpoint Files", "*.pth")])
    if ckpt_file:
        ckpt_entry_var.set(ckpt_file)

def on_file_exit():
    app.quit()


def browse_ckpt_file():
    ckpt_file = filedialog.askopenfilename(initialdir="./ckpt", filetypes=[("Checkpoint Files", "*.pth")])
    if ckpt_file:
        ckpt_entry_var.set(ckpt_file)

def on_type_select(*args):
    selected_type = type_var.get()
    if selected_type == "Custom Image":
        custom_image_label.pack(pady=5, anchor='w')
        custom_image_entry.pack(pady=5, anchor='w')
        custom_image_button.pack(pady=5, anchor='w')
    else:
        custom_image_label.pack_forget()
        custom_image_entry.pack_forget()
        custom_image_button.pack_forget()

def browse_custom_image():
    custom_image_file = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.png")])
    custom_image_entry.delete(0, tk.END)
    custom_image_entry.insert(0, custom_image_file)

def show_about():
    # Placeholder function for showing application information or help content
    about_text = "This is a background removal application created by ©Pushpendra Sharma in association with ©Spark VFX Studios.\nVersion: 1.0"
    tk.messagebox.showinfo("About", about_text)



# Function to handle the background removal process
def perform_background_removal():
    try:
        # Get the file path selected by the user
        source_path = source_entry.get()
        destination_path = destination_entry.get()
        ckpt_path = ckpt_entry_var.get()
        jit_enabled = jit_var.get()
        fast_enabled = fast_var.get()
        selected_device = device_var.get()  # Get the selected device from the dropdown menu
        selected_type = type_var.get()  # Get the selected background type

        # Validate if the required fields are filled
        if not source_path or not destination_path or not ckpt_path:
            print("Please fill all required fields.")
            return

        # Check if the source path is a video file (.mp4)
        is_video = source_path.lower().endswith('.mp4')

        # Create a Remover instance
        if selected_device == "GPU":
            remover = Remover(fast=fast_enabled, jit=jit_enabled, device="cuda", ckpt=ckpt_path)
        else:
            remover = Remover(fast=fast_enabled, jit=jit_enabled, device="cpu", ckpt=ckpt_path)

        global abort_requested
        abort_requested = False

        global original_preview_label, processed_preview_label  # Declare global variables for the preview labels
        original_preview_label = tk.Label(app)
        original_preview_label.pack(side=tk.LEFT, padx=10, pady=10)  # Pack the original frame preview label
        
        processed_preview_label = tk.Label(app)
        processed_preview_label.pack(side=tk.RIGHT, padx=10, pady=10)  # Pack the processed frame preview label

        if is_video:
            # Load the video using cv2
            cap = cv2.VideoCapture(source_path)
            if not cap.isOpened():
                print("Error opening video file.")
                return

            # Get video details
            frame_width = int(cap.get(3))
            frame_height = int(cap.get(4))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            # Create VideoWriter to save the result video
            # Create VideoWriter to save the result video
            output_file = os.path.join(destination_path, os.path.splitext(os.path.basename(source_path))[0] +"_"+selected_type+"_processed.mp4")
            out = cv2.VideoWriter(output_file, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))


            # Create progress bar and abort button
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(app, variable=progress_var, maximum=100)
            progress_bar.pack(pady=5, anchor='w')

            frame_count_label = tk.Label(app, text="Frame Count: 0/0")
            frame_count_label.pack(pady=5, anchor='w')

            # Abort button
            abort_button = tk.Button(app, text="Abort", command=abort_background_removal)
            abort_button.pack(pady=5, anchor='w')

            # Start background removal in a separate thread
            background_thread = threading.Thread(target=background_removal_thread, args=(remover, cap, out, total_frames, progress_var, frame_count_label, progress_bar, original_preview_label, processed_preview_label, abort_button, selected_type))
            background_thread.start()
        else:
            # Load the image using PIL
            image = Image.open(source_path)

            # Perform background removal on the image
            result_array = remover.process(image, type='rgba')
            result_image = Image.fromarray(result_array)
            # Save the result image to the destination folder
            result_image.save(os.path.join(destination_path, "background_removed.png"))

            print("Background removal for image completed. Result saved to:", os.path.join(destination_path, "background_removed.png"))
    except Exception as e:
        print(f"An error occurred: {e}")
    

def background_removal_thread(remover, cap, out, total_frames, progress_var, frame_count_label, progress_bar, original_preview_label, processed_preview_label, abort_button, selected_type):
    global abort_requested
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret or abort_requested:
            break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame).convert('RGB')

        out_img = remover.process(img, type=selected_type)
        out_frame = cv2.cvtColor(np.array(out_img), cv2.COLOR_RGB2BGR)
        out.write(out_frame)

        # Convert frames to PhotoImage format suitable for tkinter
        original_img = Image.fromarray(frame)
        original_img = original_img.resize((320, 240), Image.ANTIALIAS)
        original_img = ImageTk.PhotoImage(image=original_img)

        processed_img = Image.fromarray(out_img)
        processed_img = processed_img.resize((320, 240), Image.ANTIALIAS)
        processed_img = ImageTk.PhotoImage(image=processed_img)

        # Update preview labels with new images
        original_preview_label.config(image=original_img)
        original_preview_label.image = original_img  # Keep a reference to prevent garbage collection

        processed_preview_label.config(image=processed_img)
        processed_preview_label.image = processed_img  # Keep a reference to prevent garbage collection

        # Update progress bar and frame count label
        frame_count += 1
        progress_var.set(frame_count)
        frame_count_label.config(text=f"Frame Count: {frame_count}/{total_frames}")

        app.update_idletasks()
        
        # Sleep for a short duration to release the GIL and allow GUI updates
        time.sleep(0.01)

    # Release video capture and writer objects
    cap.release()
    out.release()

    # Hide progress bar, frame count label, and preview labels after processing
    progress_bar.pack_forget()  # Corrected this line to use progress_bar instead of progress_var
    frame_count_label.pack_forget()
    original_preview_label.pack_forget()
    processed_preview_label.pack_forget()
    abort_button.pack_forget()
    if abort_requested:
        print("Background removal process aborted.")
    else:
        print("Background removal for video completed.")

def abort_background_removal():
    global abort_requested
    abort_requested = True


# Create the main application window
app = tk.Tk()
app.title("Video and Image Background Settings")

# Menubar
menubar = tk.Menu(app)
app.config(menu=menubar)

# File Menu
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Open CKPT File", command=on_file_open)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=on_file_exit)
menubar.add_cascade(label="File", menu=file_menu)

# Help menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="About", command=show_about)

# Create a StringVar to store the CKPT file path
ckpt_entry_var = tk.StringVar()

# CKPT File Entry (hidden in the UI, used to store the selected file path)
ckpt_entry_label = tk.Label(app, text="Checkpoint FIle Path:")
ckpt_entry_label.pack(pady=5, anchor='w')
ckpt_entry = tk.Entry(app, textvariable=ckpt_entry_var, state='disabled')
ckpt_entry.pack(pady=5, anchor='w')

# Set the default ckpt file from the ckpt folder
set_default_ckpt_file()

# Source Path Entry
source_path_label = tk.Label(app, text="Source Path:")
source_path_label.pack(pady=5, anchor='w')

source_entry = tk.Entry(app, width=40)
source_entry.pack(pady=5, anchor='w')

source_button = tk.Button(app, text="Browse", command=browse_source_path)
source_button.pack(pady=5, anchor='w')

# Destination Path Entry
destination_label = tk.Label(app, text="Destination Path:")
destination_label.pack(pady=5, anchor='w')

destination_entry = tk.Entry(app, width=40)
destination_entry.pack(pady=5, anchor='w')

destination_button = tk.Button(app, text="Browse", command=browse_destination_folder)
destination_button.pack(pady=5, anchor='w')

# Type Selection
type_label = tk.Label(app, text="Select Background Type:")
type_label.pack(pady=5, anchor='w')

background_types = ["map", "green", "white", "blur", "overlay", "Custom Image"]
type_var = tk.StringVar(value=background_types[0])  # Set default background type to "map"
type_dropdown = ttk.Combobox(app, values=background_types, textvariable=type_var, state="readonly")
type_dropdown.pack(pady=5, anchor='w')
type_var.trace("w", on_type_select)
# Custom Image Entry
custom_image_label = tk.Label(app, text="Custom Image Path:")
custom_image_label.pack_forget()  # Initially hide the custom image entry
custom_image_entry = tk.Entry(app, width=40)
custom_image_entry.pack_forget()  # Initially hide the custom image entry
custom_image_button = tk.Button(app, text="Browse", command=browse_custom_image)
custom_image_button.pack_forget()  # Initially hide the custom image entry

# JIT Option
jit_var = tk.BooleanVar(value=False)
jit_checkbox = tk.Checkbutton(app, text="Enable JIT", variable=jit_var)
jit_checkbox.pack(pady=5, anchor='w')

# FAST Option
fast_var = tk.BooleanVar(value=False)
fast_checkbox = tk.Checkbutton(app, text="Enable FAST", variable=fast_var)
fast_checkbox.pack(pady=5, anchor='w')

# Device Selection
device_label = tk.Label(app, text="Select Device:")
device_label.pack(pady=5, anchor='w')

devices = ["CPU", "GPU"]
device_var = tk.StringVar(value=devices[0])  # Set default device to CPU
device_dropdown = ttk.Combobox(app, values=devices, textvariable=device_var, state="readonly")
device_dropdown.pack(pady=5, anchor='w')

# Start Background Removal Button
background_removal_button = tk.Button(app, text="Start Background Removal", command=perform_background_removal)
background_removal_button.pack(pady=10, anchor='w')

# Initialize the abort_requested list to False
abort_requested = False

# Start the main event loop
app.mainloop()
