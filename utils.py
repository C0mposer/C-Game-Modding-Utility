import struct
import send2trash
from tkinter import filedialog
import platform
import os

### Module of little utility functions used throughout the project

def flip_endianness(data):
    # Convert data to a list of 4-byte chunks
    chunks = [data[i:i+4] for i in range(0, len(data), 4)]
    
    # Flip endianness for each chunk
    flipped_chunks = [struct.pack('<I', struct.unpack('>I', chunk)[0]) for chunk in chunks]
    
    # Concatenate the flipped chunks
    flipped_data = b''.join(flipped_chunks)
    
    return flipped_data

def flip_file_endianness(file_path):
    with open(file_path, 'rb') as file:
        data = file.read()
    
    flipped_data = flip_endianness(data)
    
    with open(file_path, 'wb') as file:
        file.write(flipped_data)
        
def MoveToRecycleBin(path):
    try:
        send2trash.send2trash(path)
        print(f'Successfully moved {path} to the recycle bin.')
    except Exception as e:
        print(f'Error moving {path} to the recycle bin: {e}')
     
def find_files_with_extension(directory, extension):
    files_with_extension = []
    
    # Iterate through all files in the directory
    for filename in os.listdir(directory):
        # Check if the file ends with the desired extension
        if filename.endswith(extension):
            files_with_extension.append(os.path.join(directory, filename))

    return files_with_extension  

def open_output_directory():
    return filedialog.askdirectory(title="Choose output directory") 


def IsOnWindows():
    if platform.platform().startswith("Windows"):
        return True    
def IsOnLinux():
    if platform.platform().startswith("Linux"):
        return True    
    
def IsOnWineLinux():
    # Wine sets the 'WINELOADERNOEXEC' environment variable
    if 'WINELOADERNOEXEC' in os.environ:
        return True
    # Alternatively, check for 'WINEPREFIX'
    if 'WINEPREFIX' in os.environ:
        return True
    return False