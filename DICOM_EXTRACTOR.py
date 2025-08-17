import os
import zipfile
import pydicom
import numpy as np
from PIL import Image, ImageTk, ImageOps
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import shutil
from datetime import datetime
import threading
import tempfile
import sys
import subprocess
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

def extract_zip(zip_path, extract_to):
    """Extract zip file to specified directory"""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    return extract_to

def find_dicom_files(folder_path):
    """Recursively find DICOM files in the given folder"""
    dicom_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                # Check if file is a DICOM file by reading the first 132 bytes
                with open(file_path, 'rb') as f:
                    content = f.read(132)  # Read first 132 bytes to check DICOM signature
                    if is_dicom_file_content(content):
                        dicom_files.append(file_path)
            except Exception as e:
                print(f"Error checking {file_path}: {e}")
    return dicom_files

def process_dicom(dicom_path):
    """Process a single DICOM file and return image data"""
    try:
        # Skip DICOMDIR files as they don't contain image data
        if os.path.basename(dicom_path).upper() == 'DICOMDIR':
            print(f"Skipping DICOM directory file: {dicom_path}")
            return None, None
            
        try:
            # Try reading with force=True to handle more DICOM variations
            ds = pydicom.dcmread(dicom_path, force=True)
            
            # Check if this DICOM file contains pixel data
            if not hasattr(ds, 'pixel_array'):
                print(f"Skipping non-image DICOM file: {dicom_path}")
                return None, None
                
            # Get pixel array
            try:
                pixel_array = ds.pixel_array
            except Exception as e:
                print(f"Error reading pixel data from {dicom_path}: {str(e)}")
                return None, None
                
            # Convert to float for processing
            try:
                image_2d = pixel_array.astype(float)
                
                # Handle different photometric interpretations
                photometric = getattr(ds, 'PhotometricInterpretation', '')
                if photometric == 'MONOCHROME1':
                    # Invert grayscale if needed
                    image_2d = np.max(image_2d) - image_2d
                
                # Rescale to 0-255 range
                max_val = np.max(image_2d)
                min_val = np.min(image_2d)
                
                if max_val > min_val:  # Avoid division by zero
                    image_2d = 255.0 * (image_2d - min_val) / (max_val - min_val)
                
                # Convert to uint8
                image_2d = np.clip(image_2d, 0, 255).astype(np.uint8)
                
                return image_2d, ds
                
            except Exception as e:
                print(f"Error processing pixel data in {dicom_path}: {str(e)}")
                return None, None
                
        except Exception as e:
            print(f"Error reading DICOM file {dicom_path}: {str(e)}")
            return None, None
            
    except Exception as e:
        print(f"Unexpected error with {dicom_path}: {str(e)}")
        return None, None

def is_dicom_file_content(file_content):
    """Check if the given file content is a DICOM file"""
    try:
        # Check for DICOM magic number (DICM at position 128)
        if len(file_content) >= 132 and file_content[128:132] == b'DICM':
            return True
            
        # Some DICOM files don't have the magic number but start with a valid DICOM prefix
        if len(file_content) >= 4 and file_content.startswith((b'\x01\x00', b'\x02\x00', b'\x08\x00')):
            return True
    except:
        pass
    return False

def check_zip_contents(zip_path):
    """Check the contents of a ZIP file and count DICOM files"""
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Get all file names in the ZIP
            all_files = zf.namelist()
            print(f"Total files in ZIP: {len(all_files)}")
            
            # Find DICOM files by content
            dicom_files = []
            for file_name in all_files:
                try:
                    # Skip directories and non-DICOM files by extension first (faster check)
                    if not file_name.endswith('/'):  # Skip directories
                        with zf.open(file_name) as f:
                            content = f.read(132)  # Read first 132 bytes to check DICOM signature
                            if is_dicom_file_content(content):
                                dicom_files.append(file_name)
                except Exception as e:
                    print(f"  Warning: Could not check {file_name}: {str(e)}")
            
            print(f"DICOM files found: {len(dicom_files)}")
            
            # Print first 10 file names with DICOM status
            print("\nFirst 10 files in ZIP:")
            for i, f in enumerate(all_files[:10], 1):
                status = "(DICOM)" if f in dicom_files else ""
                print(f"  {i}. {f} {status}")
                
            return len(dicom_files)
    except Exception as e:
        print(f"Error checking ZIP file: {str(e)}")
        return 0

def process_dicom_folder(folder_path):
    """Process all DICOM files in a folder"""
    output_dir = os.path.join(folder_path, 'extracted_images')
    os.makedirs(output_dir, exist_ok=True)
    
    def process_dicom_file(self, dicom_path, output_dir, file_index, total_files):
        print(f"\nProcessing file {file_index + 1} of {total_files}: {os.path.basename(dicom_path)}")
        
        try:
            # Try to read the DICOM file with force=True to handle most cases
            try:
                # First try with standard reading
                print("  - Attempting standard DICOM read...")
                ds = pydicom.dcmread(dicom_path, force=True)
                print("  - Successfully read DICOM file")
                
            except Exception as e:
                print(f"  - Error reading with standard method: {str(e)}")
                print("  - Trying with defer_size...")
                
                # If that fails, try with defer_size
                try:
                    ds = pydicom.dcmread(dicom_path, force=True, defer_size='1 KB')
                    print("  - Successfully read with defer_size")
                except Exception as e2:
                    print(f"  - Failed to read DICOM: {str(e2)}")
                    if not HAS_PYLIBJPEG and ('decompression' in str(e2).lower() or 'jpeg' in str(e2).lower()):
                        print("\nERROR: This DICOM file uses JPEG compression which requires additional packages.")
                        print("Please install the required packages by running:")
                        print("pip install pylibjpeg pylibjpeg-libjpeg")
                        print("Or if you're using conda:")
                        print("conda install -c conda-forge pylibjpeg pylibjpeg-libjpeg")
                    return None
            
            # Check if the DICOM has pixel data
            if hasattr(ds, 'pixel_array'):
                try:
                    print("  - Extracting pixel data...")
                    # Try to get the pixel array
                    if HAS_PYLIBJPEG and hasattr(ds, 'file_meta') and 'JPEG' in str(ds.file_meta.get('TransferSyntaxUID', '')):
                        print("  - Using pylibjpeg for JPEG compressed DICOM")
                        img = get_pixel_data(ds)
                    else:
                        print("  - Using standard pixel_array extraction")
                        img = ds.pixel_array
                    
                    print(f"  - Extracted image dimensions: {img.shape if hasattr(img, 'shape') else 'N/A'}")
                except Exception as e:
                    print(f"Error reading pixel data from {dicom_path}: {str(e)}")
                    if 'decompression' in str(e).lower():
                        print("Trying to handle compressed DICOM...")
                        try:
                            # Try to handle specific compression formats
                            if 'jpeg' in str(e).lower():
                                print("JPEG compression detected. Installing required packages...")
                                print("Please run the following command in your terminal:")
                                print("pip install pylibjpeg pylibjpeg-libjpeg")
                                print("Or if you're using conda:")
                                print("conda install -c conda-forge pylibjpeg pylibjpeg-libjpeg")
                            return None
                        except Exception as inner_e:
                            print(f"Failed to handle compressed DICOM: {str(inner_e)}")
                            return None
                
                # Normalize the image
                try:
                    print("  - Normalizing image...")
                    img = self.normalize_image(img)
                    
                    # Convert to 8-bit
                    img = (img * 255).astype('uint8')
                    
                    # Generate output filename
                    output_filename = f"dicom_{file_index:04d}.png"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # Save as PNG
                    print(f"  - Saving image to {output_path}...")
                    cv2.imwrite(output_path, img)
                    print(f"  - Successfully saved {output_filename}")
                    
                    return output_path
                except Exception as e:
                    print(f"  - Error processing image: {str(e)}")
                    return None
            else:
                print(f"No pixel data found in {dicom_path}")
                return None
                
        except Exception as e:
            print(f"Error processing {dicom_path}: {str(e)}")
            return None
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.dcm', '.dicom')):
                dicom_path = os.path.join(root, file)
                output_path = process_dicom_file(self=None, dicom_path=dicom_path, output_dir=output_dir, file_index=0, total_files=0)
                
                if output_path is not None:
                    # Print DICOM metadata
                    ds = pydicom.dcmread(dicom_path)
                    print(f"\nDICOM Info for {file}:")
                    print(f"Patient Name: {getattr(ds, 'PatientName', 'N/A')}")
                    print(f"Study Date: {getattr(ds, 'StudyDate', 'N/A')}")
                    print(f"Modality: {getattr(ds, 'Modality', 'N/A')}")
                    print(f"Image Size: {ds.pixel_array.shape}")
                    print("-" * 50)

class DICOMExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)  # Set minimum window size
        self.image_paths = []  # Store paths to extracted images
        self._resize_id = None  # For debouncing window resize events
        self.current_previews = []  # Store current preview widgets
        
        # Enable drag and drop
        self.root.drop_target_register('DND_Files')
        self.root.dnd_bind('<<Drop>>', self.on_drop)
        self.root.dnd_bind('<<DropEnter>>', self.on_drop_enter)
        self.root.dnd_bind('<<DropLeave>>', self.on_drop_leave)
        
        # Configure style
        self.style = ttk.Style()
        self.style.configure('TFrame', padding=10)
        self.style.configure('TButton', padding=5)
        
        # Main container with proper weight configuration
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        
        # Title frame to contain the title and instructions
        title_frame = ttk.Frame(self.main_frame)
        title_frame.grid(row=0, column=0, sticky="ew")
        title_frame.columnconfigure(0, weight=1)
        
        # Title with reduced bottom padding
        title = ttk.Label(
            title_frame, 
            text="DICOM EXTRACTOR", 
            font=('Helvetica', 16, 'bold')
        )
        title.grid(row=0, column=0, pady=(0, 5), sticky="n")
        
        # Instructions with reduced bottom padding
        instructions = ttk.Label(
            title_frame,
            text="Select ZIP files containing DICOM files",
            wraplength=500,
            justify=tk.CENTER
        )
        instructions.grid(row=1, column=0, pady=(0, 5), sticky="n")
        
        # File selection with proper expansion
        self.file_frame = ttk.Frame(self.main_frame)
        self.file_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        self.file_frame.columnconfigure(0, weight=1)
        self.file_frame.rowconfigure(0, weight=1)  # Allow the file list to expand
        
        # Text widget for displaying multiple files
        text_frame = ttk.Frame(self.file_frame)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar for the text widget
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.file_text = tk.Text(
            text_frame,
            height=4,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set
        )
        self.file_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.config(command=self.file_text.yview)
        
        # Store file paths
        self.file_path = tk.StringVar()
        self.file_text.bind('<Key>', lambda e: 'break')  # Make read-only
        
        # Button frame
        btn_frame = ttk.Frame(self.file_frame)
        btn_frame.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.browse_btn = ttk.Button(
            btn_frame, 
            text="Add ZIP Files...", 
            command=self.browse_file,
            width=15
        )
        self.browse_btn.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        self.clear_btn = ttk.Button(
            btn_frame,
            text="Clear List",
            command=self.reset_application,
            width=15
        )
        self.clear_btn.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        self.export_btn = ttk.Button(
            btn_frame,
            text="Export Images",
            command=self.export_images,
            width=15
        )
        self.export_btn.pack(side=tk.TOP, fill=tk.X)
        
        # Progress and status frame with reduced top padding
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        status_frame.columnconfigure(0, weight=1)
        
        # Progress bar with improved styling
        self.progress = ttk.Progressbar(
            status_frame, 
            orient=tk.HORIZONTAL, 
            mode='determinate',
            style='green.Horizontal.TProgressbar'
        )
        self.progress.pack(side=tk.TOP, fill=tk.X, expand=True)
        
        # Configure progress bar style
        style = ttk.Style()
        style.theme_use('default')
        style.configure('green.Horizontal.TProgressbar',
            background='#4CAF50',
            troughcolor='#f0f0f0',
            bordercolor='#4CAF50',
            lightcolor='#8BC34A',
            darkcolor='#388E3C',
            thickness=20,
            troughrelief='flat',
            borderwidth=1
        )
        
        # Make sure the progress bar is visible even at 0%
        self.progress['value'] = 0
        self.progress.update()
        
        # Canvas for image previews
        self.canvas_frame = ttk.Frame(self.main_frame)
        self.canvas_frame.grid(row=5, column=0, sticky="nsew")
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_frame.rowconfigure(0, weight=1)
        
        # Create a canvas with scrollbars
        self.canvas = tk.Canvas(self.canvas_frame, bg='#f0f0f0')
        self.scrollbar_y = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_x = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(
            yscrollcommand=self.scrollbar_y.set,
            xscrollcommand=self.scrollbar_x.set
        )
        
        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.scrollbar_x.grid(row=1, column=0, sticky="ew")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind mouse wheel for scrolling
        def _on_mousewheel(event):
            if event.num == 4 or event.delta == 120:  # Scroll up
                self.canvas.yview_scroll(-6, "units")
            elif event.num == 5 or event.delta == -120:  # Scroll down
                self.canvas.yview_scroll(6, "units")
        
        # For Windows and MacOS
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # For Linux
        self.canvas.bind_all("<Button-4>", _on_mousewheel)
        self.canvas.bind_all("<Button-5>", _on_mousewheel)
        # Make sure scrolling works when mouse is over the canvas
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        
        # Process button
        self.process_btn = ttk.Button(
            self.main_frame, 
            text="EXTRACT DICOM IMAGES", 
            command=self.start_processing,
            style='Accent.TButton'
        )
        self.process_btn.grid(row=4, column=0, pady=10, sticky="ew")
        
        # Configure the grid to be responsive
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(5, weight=1)  # Make the canvas row expandable
        
        # Bind window resize event after the window is fully initialized
        self.root.after(100, self._bind_resize_event)
    
    def _clear_previews(self):
        """Clear all preview widgets"""
        if not hasattr(self, 'scrollable_frame'):
            return
            
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.current_previews = []
    
    def _bind_resize_event(self):
        """Bind the window resize event after the window is fully initialized"""
        self.root.bind('<Configure>', self.on_window_resize)
        # Initial update after a short delay to ensure window is ready
        self.root.after(100, self._delayed_initial_update)
    
    def _delayed_initial_update(self):
        """Handle initial window sizing"""
        if hasattr(self, 'current_image_paths'):
            self.show_image_previews(self.current_image_paths)
    
    def on_drop_enter(self, event):
        """Handle drag enter event"""
        return 'copy'
    
    def on_drop_leave(self, event):
        """Handle drag leave event"""
        pass
    
    def export_images(self):
        """Export the extracted images to a selected directory"""
        if not hasattr(self, 'current_image_paths') or not self.current_image_paths:
            messagebox.showinfo("No Images", "No extracted images available to export.")
            return
            
        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if not export_dir:
            return
            
        success_count = 0
        try:
            for img_path in self.current_image_paths:
                if os.path.exists(img_path):
                    dest_path = os.path.join(export_dir, os.path.basename(img_path))
                    shutil.copy2(img_path, dest_path)
                    success_count += 1
            
            if success_count > 0:
                messagebox.showinfo(
                    "Export Complete", 
                    f"Successfully exported {success_count} image(s) to:\n{export_dir}"
                )
            else:
                messagebox.showinfo("Export Failed", "No images were exported.")
                
        except Exception as e:
            messagebox.showerror(
                "Export Error", 
                f"Failed to export images: {str(e)}\n\n"
                f"Successfully exported {success_count} images before the error occurred."
            )
    
    def reset_application(self):
        """Reset the application to its initial state"""
        self.file_text.delete(1.0, tk.END)
        self.progress['value'] = 0
        self.root.title("")
        self.process_btn.config(state=tk.NORMAL)
        self.browse_btn.config(state=tk.NORMAL)
        
    def is_dicom_file(self, file_path):
        """Check if a file is a DICOM file"""
        try:
            # Quick check by extension first (faster)
            if file_path.lower().endswith(('.dcm', '.dicom', '.ima')):
                return True
            # Then check file signature
            with open(file_path, 'rb') as f:
                header = f.read(132)  # DICOM header is at least 132 bytes
                return header[128:132] == b'DICM'
        except:
            return False
    
    def scan_for_dicom(self, path):
        """Recursively scan a path for DICOM files"""
        dicom_files = []
        
        if os.path.isfile(path):
            if self.is_dicom_file(path) or path.lower().endswith('.zip'):
                return [path]
            return []
            
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_dicom_file(file_path) or file.lower().endswith('.zip'):
                    dicom_files.append(file_path)
        
        return dicom_files

    def on_drop(self, event):
        """Handle file/folder drop event"""
        try:
            paths = self.root.tk.splitlist(event.data)
            valid_paths = []
            
            for path in paths:
                if os.path.isdir(path) or os.path.isfile(path):
                    if os.path.isfile(path) and (path.lower().endswith('.zip') or self.is_dicom_file(path)):
                        valid_paths.append(path)
                    elif os.path.isdir(path):
                        valid_paths.extend(self.scan_for_dicom(path))
            
            # Update the file list with new valid paths
            if valid_paths:
                current_files = self.file_text.get('1.0', tk.END).splitlines()
                current_files = [f.strip() for f in current_files if f.strip()]
                
                # Add only new files that aren't already in the list
                new_files = [f for f in valid_paths if f not in current_files]
                
                if new_files:
                    for path in new_files:
                        self.file_text.insert(tk.END, path + '\n')
                    self.file_path.set("\n".join(set(current_files + new_files)))
                    if hasattr(self, 'image_paths') and self.image_paths:
                        self.root.after(100, lambda: self.show_image_previews(self.image_paths))
                        if hasattr(self, 'canvas'):
                            self.canvas.yview_moveto(0)  # Scroll to top
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred while processing files:\n{str(e)}")
    
    def on_window_resize(self, event):
        """Handle window resize events to update the preview layout"""
        if event.widget == self.root:  # Only handle root window resize
            if hasattr(self, '_resize_id') and self._resize_id is not None:
                try:
                    self.root.after_cancel(self._resize_id)
                except:
                    pass  # Ignore errors from invalid after_id
            self._resize_id = self.root.after(200, self._delayed_resize)
    
    def _delayed_resize(self):
        """Handle delayed window resize to prevent excessive updates"""
        if hasattr(self, 'current_image_paths') and self.current_image_paths:
            try:
                # Store scroll position
                x_view = self.canvas.xview()[0]
                y_view = self.canvas.yview()[0]
                
                # Update previews
                current_paths = self.current_image_paths.copy()
                self.show_image_previews(current_paths)
                
                # Restore scroll position
                self.canvas.xview_moveto(x_view)
                self.canvas.yview_moveto(y_view)
            except Exception as e:
                print(f"Error updating previews: {e}")
    
    def browse_file(self):
        """Open file dialog to select DICOM files, ZIPs, or folders"""
        # Show file dialog that allows multiple file and folder selection
        file_paths = filedialog.askopenfilenames(
            title="Select DICOM files, ZIP archives, or folders",
            filetypes=[
                ("DICOM, ZIP, and Folders", "*.dcm *.dicom *.DCM *.DICOM *.ima *.IMA *.zip *.ZIP"),
                ("All files", "*.*")
            ]
        )
        
        valid_paths = []
        
        if file_paths:
            for path in file_paths:
                if os.path.isfile(path):
                    if path.lower().endswith('.zip') or self.is_dicom_file(path):
                        valid_paths.append(path)
                elif os.path.isdir(path):
                    valid_paths.extend(self.scan_for_dicom(path))
        
        # Update the file list with valid paths
        if valid_paths:
            # Clear existing content
            self.file_text.delete(1.0, tk.END)
            
            # Add all valid paths to the text widget
            for path in valid_paths:
                self.file_text.insert(tk.END, path + '\n')
            self.file_path.set("\n".join(valid_paths))
            
            # If we have image paths, update the preview
            if hasattr(self, 'image_paths') and self.image_paths:
                self.root.after(100, lambda: self.show_image_previews(self.image_paths))
        elif file_paths:  # Only show message if user actually selected something but no valid files were found
            messagebox.showinfo("No Valid Files", "No DICOM or ZIP files found in the selected location.")
    
    def update_status(self, message, progress=None):
        """Update the progress bar and window title with status"""
        self.root.title(f"{message}")
        if progress is not None:
            self.progress['value'] = progress
            self.root.update_idletasks()
        else:
            self.progress['value'] = 0
            self.root.update_idletasks()
    
    def start_processing(self):
        # Get paths from the text widget and clean them up
        zip_paths = [p.strip() for p in self.file_text.get('1.0', tk.END).split('\n') if p.strip()]
        
        # Remove any empty strings that might have been created
        zip_paths = [p for p in zip_paths if p]
        
        if not zip_paths:
            messagebox.showerror("Error", "Please add at least one file or folder first!")
            return
            
        self.processing_multiple = len(zip_paths) > 1  # Set flag for multiple files
        
        # Validate all files
        valid_paths = []
        for path in zip_paths:
            if os.path.isfile(path) and (path.lower().endswith('.zip') or self.is_dicom_file(path)):
                valid_paths.append(path)
            elif os.path.isdir(path):
                valid_paths.extend(self.scan_for_dicom(path))
        
        if not valid_paths:
            messagebox.showerror("Error", "No valid DICOM or ZIP files found in the selected items!")
            return
        
        # Disable buttons during processing
        self.process_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        
        # Reset progress
        self.progress['value'] = 0
        self.root.update_idletasks()
        
        # Start processing in a separate thread to keep the UI responsive
        self.thread = threading.Thread(
            target=self.process_multiple_zips,
            args=(valid_paths,),
            daemon=True
        )
        self.thread.start()
        
        # Check thread status periodically
        self.check_thread()
    
    def process_multiple_zips(self, file_paths):
        """Process multiple files or folders sequentially"""
        total_files = len(file_paths)
        all_image_paths = []
        
        for i, file_path in enumerate(file_paths, 1):
            current_progress = (i - 1) * 100 // total_files
            self.update_status(f"Processing {i} of {total_files}: {os.path.basename(file_path)[:30]}...", 
                             current_progress)
            
            if file_path.lower().endswith('.zip'):
                output_dir = self.process_zip(file_path, i-1, total_files)
                
                # Collect all image paths from this output directory
                if output_dir and os.path.exists(output_dir):
                    for root, _, files in os.walk(output_dir):
                        for file in files:
                            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                                all_image_paths.append(os.path.join(root, file))
            else:
                # Process single DICOM file
                try:
                    output_dir = os.path.join(os.path.expanduser("~"), "DICOM_Extracted", "Single_Files")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Process the DICOM file
                    image_data, ds = process_dicom(file_path)
                    if image_data is not None:
                        # Create a descriptive filename
                        study_date = getattr(ds, 'StudyDate', 'unknown_date')
                        sop_instance_uid = getattr(ds, 'SOPInstanceUID', str(i))
                        output_filename = f"{study_date}_{sop_instance_uid}.png"
                        output_path = os.path.join(output_dir, output_filename)
                        
                        # Save the image
                        if OPENCV_AVAILABLE:
                            cv2.imwrite(output_path, image_data)
                        else:
                            img = Image.fromarray(image_data) if len(image_data.shape) == 2 else \
                                  Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
                            img.save(output_path)
                        
                        all_image_paths.append(output_path)
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
        
        # Update progress to 100%
        self.update_status("Processing complete!", 100)
        
        # Show all extracted images in preview
        if all_image_paths:
            self.root.after(100, lambda: self.show_image_previews(all_image_paths))
    
    def check_thread(self):
        if self.thread.is_alive():
            self.root.after(100, self.check_thread)
        else:
            self.process_btn.config(state=tk.NORMAL)
            self.browse_btn.config(state=tk.NORMAL)
            
            # Show completion message if processing was successful
            if self.progress['value'] == 100:
                self.update_status("✅ Processing completed successfully!")
    
    def open_image(self, image_path):
        """Open image in default system viewer"""
        try:
            if os.name == 'nt':  # For Windows
                os.startfile(image_path)
            elif os.name == 'posix':  # For macOS and Linux
                if os.uname().sysname == 'Darwin':
                    os.system(f'open "{image_path}"')
                else:
                    os.system(f'xdg-open "{image_path}"')
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image: {str(e)}")
    
    def show_image_previews(self, image_paths):
        """Display thumbnails of the extracted images"""
        if not hasattr(self, 'scrollable_frame') or not image_paths:
            return
            
        # Store the current image paths for resize events
        self.current_image_paths = image_paths
        
        # Clear previous previews
        self._clear_previews()
        
        # Calculate available width for previews
        window_width = self.canvas.winfo_width()
        if window_width < 1:
            window_width = 800  # Default width if not yet rendered
        
        # Calculate number of columns based on window width
        window_width = self.canvas.winfo_width()
        if window_width < 1:  # In case window isn't mapped yet
            window_width = 800  # Default width
            
        # Calculate number of columns (minimum 2, maximum 6)
        self.current_columns = max(2, min(6, window_width // 200))  # Each image takes ~200px
        
        # Group images by their parent directory (ZIP file)
        zip_groups = {}
        for img_path in image_paths:
            zip_name = os.path.basename(os.path.dirname(os.path.dirname(img_path)))
            if zip_name not in zip_groups:
                zip_groups[zip_name] = []
            zip_groups[zip_name].append(img_path)
        
        # Show previews grouped by ZIP file
        for zip_name, img_list in zip_groups.items():
            # Add ZIP file header
            header = ttk.Label(
                self.scrollable_frame,
                text=f"ZIP: {zip_name}",
                font=('Helvetica', 10, 'bold'),
                background='#f0f0f0',
                padding=(10, 5, 10, 5)
            )
            header.pack(fill=tk.X, pady=(10, 5), padx=5)
            
            # Create a frame for the preview row
            preview_frame = ttk.Frame(self.scrollable_frame)
            preview_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Create a frame for each row of previews
            row_frame = ttk.Frame(preview_frame)
            row_frame.pack(fill=tk.X)
            
            for i, img_path in enumerate(img_list):
                try:
                    # Start a new row after every 'max_columns' images
                    if i > 0 and i % self.current_columns == 0:
                        row_frame = ttk.Frame(preview_frame)
                        row_frame.pack(fill=tk.X)
                    
                    # Create a frame for each image preview
                    img_frame = ttk.Frame(row_frame, padding=5, relief='groove', borderwidth=1)
                    img_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=True)
                    
                    # Load and resize image for preview
                    img = Image.open(img_path)
                    
                    # Get target size based on window width
                    cols = max(2, min(6, self.canvas.winfo_width() // 200))  # Target 200px per image
                    target_size = (self.canvas.winfo_width() // cols) - 30  # Account for padding
                    
                    # Maintain aspect ratio
                    aspect_ratio = img.width / img.height
                    if aspect_ratio > 1:  # Landscape
                        new_width = min(target_size, img.width)
                        new_height = int(new_width / aspect_ratio)
                    else:  # Portrait or square
                        new_height = min(target_size, img.height)
                        new_width = int(new_height * aspect_ratio)
                        
                    # Resize with high-quality downsampling
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    # Create label for image with cursor change on hover
                    label = ttk.Label(img_frame, image=photo, cursor="hand2")
                    label.image = photo  # Keep a reference!
                    label.pack(pady=5)
                    
                    # Bind click event to open the image
                    label.bind('<Button-1>', lambda e, path=img_path: self.open_image(path))
                    
                    # Add filename label (clickable)
                    filename = os.path.basename(img_path)
                    filename_label = ttk.Label(
                        img_frame,
                        text=filename,
                        wraplength=150,
                        justify='center',
                        font=('Helvetica', 8),
                        cursor="hand2"
                    )
                    filename_label.pack(pady=(0, 5))
                    filename_label.bind('<Button-1>', lambda e, path=img_path: self.open_image(path))
                    
                except Exception as e:
                    print(f"Error loading image {img_path}: {e}")
            
            # Add a separator between ZIP file groups
            if len(zip_groups) > 1:
                ttk.Separator(self.scrollable_frame, orient='horizontal').pack(
                    fill=tk.X, pady=10, padx=20
                )
        
        # Update the canvas scroll region
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def process_zip(self, zip_path, current=0, total=1):
        try:
            # Only clear the UI if this is a single file operation
            if not hasattr(self, 'processing_multiple') or not self.processing_multiple:
                self.progress['value'] = 0
                for widget in self.scrollable_frame.winfo_children():
                    widget.destroy()
            
            # Create output directory with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(
                os.path.expanduser("~"), 
                "DICOM_Extracted", 
                f"{os.path.splitext(os.path.basename(zip_path))[0]}_{timestamp}"
            )
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a temp directory for extraction
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            self.update_status(f"Extracting {os.path.basename(zip_path)}...", int((current / total) * 100))
            
            try:
                # Extract the ZIP file
                extract_zip(zip_path, temp_dir)
                
                # Check if this is a DICOM study with a DICOMDIR file
                dicom_dir_path = os.path.join(temp_dir, 'DICOMDIR')
                if os.path.exists(dicom_dir_path):
                    try:
                        self.update_status("Found DICOM study directory, processing...", 
                                         int((current + 0.1) * 100 / total))
                        
                        # Use pydicom's dicomdir module to properly parse DICOMDIR
                        try:
                            # Try the new import path first (pydicom >= 2.0)
                            from pydicom.fileset import FileSet
                            use_fileset = True
                        except ImportError:
                            # Fall back to older import path (pydicom < 2.0)
                            try:
                                from pydicom.filereader import read_dicomdir
                                use_fileset = False
                            except ImportError:
                                raise ImportError("Could not find required DICOMDIR parsing modules")

                        # Process DICOMDIR
                        processed_count = 0
                        if use_fileset:
                            try:
                                fileset = FileSet(dicom_dir_path)
                                for patient in getattr(fileset, 'patients', []):
                                    for study in getattr(patient, 'studies', []):
                                        for series in getattr(study, 'series', []):
                                            for instance in getattr(series, 'instances', []):
                                                if hasattr(instance, 'filename') and os.path.exists(instance.filename):
                                                    try:
                                                        img, _ = process_dicom(instance.filename)
                                                        if img is not None:
                                                            filename = f"dicom_{len(self.image_paths) + 1}.png"
                                                            output_path = os.path.join(output_dir, filename)
                                                            img.save(output_path)
                                                            self.image_paths.append(output_path)
                                                            processed_count += 1
                                                    except Exception as e:
                                                        print(f"Error processing {instance.filename}: {e}")
                                if processed_count > 0:
                                    self.update_status(f"Processed {processed_count} DICOM files from DICOMDIR",
                                                     int((current + 0.9) * 100 / total))
                                    return
                            except Exception as e:
                                print(f"Error processing DICOMDIR with FileSet: {e}")
                        
                        # If FileSet approach failed, try the old approach
                        if processed_count == 0 and not use_fileset:
                            try:
                                dicomdir = read_dicomdir(dicom_dir_path)
                                base_dir = os.path.dirname(dicom_dir_path)
                                for patient_record in getattr(dicomdir, 'patient_records', []):
                                    for study in getattr(patient_record, 'children', []):
                                        for series in getattr(study, 'children', []):
                                            for instance in getattr(series, 'children', []):
                                                if hasattr(instance, 'ReferencedFileID') and instance.ReferencedFileID:
                                                    file_path = os.path.join(base_dir, *instance.ReferencedFileID)
                                                    if os.path.exists(file_path):
                                                        try:
                                                            img, _ = process_dicom(file_path)
                                                            if img is not None:
                                                                filename = f"dicom_{len(self.image_paths) + 1}.png"
                                                                output_path = os.path.join(output_dir, filename)
                                                                img.save(output_path)
                                                                self.image_paths.append(output_path)
                                                                processed_count += 1
                                                        except Exception as e:
                                                            print(f"Error processing {file_path}: {e}")
                                if processed_count > 0:
                                    self.update_status(f"Processed {processed_count} DICOM files from DICOMDIR",
                                                     int((current + 0.9) * 100 / total))
                                    return
                            except Exception as e:
                                print(f"Error processing DICOMDIR with read_dicomdir: {e}")
                    except Exception as e:
                        print(f"Error processing DICOMDIR: {e}")

                # If DICOMDIR processing didn't work or wasn't found, try finding DICOM files by content
                dicom_files = find_dicom_files(temp_dir)
                
                # If no DICOM files found by content, try to process all files that might be DICOM
                if not dicom_files:
                    self.update_status("No DICOM files found by signature, trying to process all files...",
                                     int((current + 0.2) * 100 / total))
                    
                    # Get all files in the extracted directory
                    all_files = []
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            # Skip DICOMDIR as we already tried that
                            if file.upper() == 'DICOMDIR':
                                continue
                            file_path = os.path.join(root, file)
                            # Skip very small files that can't be DICOM
                            if os.path.getsize(file_path) > 132:  # DICOM header is 132 bytes
                                all_files.append(file_path)
                    
                    # Try to process each file as DICOM
                    for file_path in all_files:
                        try:
                            # Try to read as DICOM
                            ds = pydicom.dcmread(file_path, force=True)
                            if hasattr(ds, 'pixel_array'):  # If it has pixel data, it's likely a valid DICOM
                                dicom_files.append(file_path)
                        except:
                            continue
                
                if not dicom_files:
                    raise Exception("No valid DICOM files found in the ZIP archive")
                
                os.makedirs(output_dir, exist_ok=True)
                
                self.update_status(f"Processing {len(dicom_files)} DICOM files from {os.path.basename(zip_path)}...",
                                 int((current + 0.2) * 100 / total))
                
                # Process each DICOM file
                total_files = len(dicom_files)
                self.image_paths = []
                
                for i, dicom_file in enumerate(dicom_files, 1):
                    # Calculate overall progress (20-100% of this file's progress)
                    file_progress = (i / total_files) * 0.8 + 0.2  # 0.2 to 1.0
                    overall_progress = int((current + file_progress) * 100 / total)
                    self.update_status(f"Processing {i}/{total_files} from {os.path.basename(zip_path)}", 
                                     min(overall_progress, 100))
                    
                    try:
                        # Process the DICOM file
                        image_data, ds = process_dicom(dicom_file)
                        if image_data is not None:
                            # Create a descriptive filename
                            study_date = getattr(ds, 'StudyDate', 'unknown_date')
                            sop_instance_uid = getattr(ds, 'SOPInstanceUID', str(i))
                            output_filename = f"{study_date}_{sop_instance_uid}.png"
                            output_path = os.path.join(output_dir, output_filename)
                            
                            # Save the image using PIL if OpenCV is not available
                            if OPENCV_AVAILABLE:
                                cv2.imwrite(output_path, image_data)
                            else:
                                # Convert numpy array to PIL Image and save
                                if len(image_data.shape) == 2:  # Grayscale
                                    img = Image.fromarray(image_data)
                                else:  # Color
                                    img = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB) if OPENCV_AVAILABLE else image_data)
                                img.save(output_path)
                                
                            self.image_paths.append(output_path)
                            
                    except Exception as e:
                        print(f"Error processing {dicom_file}: {e}")
                        continue
                
                # Show previews after processing all files
                if hasattr(self, 'image_paths') and self.image_paths:
                    self.root.after(100, lambda: self.show_image_previews(self.image_paths))
                    self.canvas.yview_moveto(0)  # Scroll to top
                
                return output_dir
                
            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            return None
    
    # Removed process_dicom_folder_with_progress as it's no longer needed

def main():
    # Check for required packages
    try:
        import pydicom
        import numpy
        from PIL import Image, ImageTk, ImageOps
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        
        # Try to import tkinterdnd2 for drag and drop
        try:
            import tkinterdnd2 as tkdnd
        except ImportError:
            if messagebox.askyesno(
                "Drag and Drop Support",
                "For drag and drop support, the tkinterdnd2 package is required.\n"
                "Would you like to install it now?"
            ):
                import subprocess
                import sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "tkinterdnd2"])
                messagebox.showinfo("Success", "Drag and drop support has been installed.\nPlease restart the application.")
                sys.exit(0)
        
        # Check for OpenCV
        try:
            import cv2
        except ImportError:
            if messagebox.askyesno(
                "OpenCV Not Found",
                "OpenCV is not installed. The application will use PIL for image processing, "
                "which may have limited functionality. Would you like to install OpenCV?"
            ):
                try:
                    import subprocess
                    import sys
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"])
                    import cv2
                    messagebox.showinfo("Success", "OpenCV installed successfully!")
                except Exception as e:
                    messagebox.showwarning(
                        "Warning",
                        f"Failed to install OpenCV: {str(e)}\n"
                        "The application will continue with limited functionality."
                    )
    except ImportError:
        import sys
        import subprocess
        import tkinter.messagebox as messagebox
        
        if messagebox.askyesno(
            "Install Required Packages",
            "This application requires some Python packages to be installed. "
            "Would you like to install them now?"
        ):
            try:
                subprocess.check_call([
                    sys.executable, 
                    "-m", 
                    "pip", 
                    "install", 
                    "pydicom", 
                    "numpy", 
                    "Pillow"
                ])
                messagebox.showinfo(
                    "Installation Complete", 
                    "Required packages installed successfully. Please restart the application."
                )
                sys.exit(0)
            except Exception as e:
                messagebox.showerror(
                    "Installation Failed", 
                    f"Failed to install required packages:\n{str(e)}\n\n"
                    "Please install them manually using:\n"
                    "pip install pydicom numpy Pillow"
                )
                sys.exit(0)
    
    # Create the main window
    root = None
    
    # Try to create window with drag and drop support
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        root.drop_target_register('DND_Files')
    except ImportError:
        try:
            import tkinterdnd2 as tkdnd
            root = tkdnd.Tk()
            root.drop_target_register('DND_Files')
        except ImportError:
            # Fallback to regular Tk if tkinterdnd2 is not available
            root = tk.Tk()
    
    # Set window icon (optional)
    try:
        # Try to use a default icon if available
        import sys
        import tempfile
        from PIL import Image, ImageTk
        
        # Create a simple icon in memory
        icon = Image.new('RGBA', (32, 32), (255, 255, 255, 0))
        
        # Create a temporary file for the icon
        temp_icon = os.path.join(tempfile.gettempdir(), 'dicom_icon.ico')
        icon.save(temp_icon, format='ICO')
        
        # Set the window icon
        root.iconbitmap(default=temp_icon)
    except Exception as e:
        # If we can't create an icon, just continue without one
        pass
    
    # Set application name for taskbar
    if os.name == 'nt':
        try:
            from ctypes import windll
            app_id = 'DICOM.Extractor.1.0'
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except:
            pass
    
    # Set window style
    style = ttk.Style()
    style.theme_use('clam')  # Use a modern theme
    
    # Configure custom styles
    style.configure('ImageFrame.TFrame', background='white', borderwidth=1, relief='solid')
    style.map('ImageFrame.TFrame',
              background=[('active', '#f0f0f0')],
              relief=[('active', 'groove')])
    
    # Create and run the application
    app = DICOMExtractorApp(root)
    
    # Set minimum window size
    window_width = 800
    window_height = 600
    root.minsize(window_width, window_height)
    
    # Bind window resize event
    root.bind('<Configure>', app.on_window_resize)
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f'{window_width}x{window_height}+{x}+{y}')
    
    # Make the window resizable
    root.minsize(600, 400)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main()
