# Step 1: Install the required packages
# pip install pyinstaller

# Step 2: Create the spec file for PyInstaller
# Save this as build_windows.py

import os
import sys
import subprocess
import shutil

def build_windows_installer():
    # Clear previous build directories if they exist
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
        
    print("Building Windows executable...")
    
    # Create icon folder if it doesn't exist
    if not os.path.exists('icons'):
        os.makedirs('icons')
    
    # Make sure icons are in the icons directory
    # You'll need to copy your .png icons there
    
    # Create executable using PyInstaller
    pyinstaller_command = [
        'pyinstaller',
        '--name=CubeCAD',
        '--windowed',  # For GUI applications
        '--onedir',    # Create a directory with all dependencies
        '--add-data=icons/*;icons/',  # Include icon resources
        '--icon=icons/place_cube_active.png',  # Set application icon
        'CubeCAD.py'
    ]
    
    subprocess.run(pyinstaller_command)
    
    print("Creating Inno Setup script...")
    
    # Create Inno Setup script
    inno_script = f'''
[Setup]
AppName=CubeCAD
AppVersion=1.0
DefaultDirName={{pf}}\\CubeCAD
DefaultGroupName=CubeCAD
OutputDir=.\\installer
OutputBaseFilename=CubeCAD_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\\CubeCAD\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{{group}}\\CubeCAD"; Filename: "{{app}}\\CubeCAD.exe"
Name: "{{commondesktop}}\\CubeCAD"; Filename: "{{app}}\\CubeCAD.exe"

[Run]
Filename: "{{app}}\\CubeCAD.exe"; Description: "Launch CubeCAD"; Flags: nowait postinstall skipifsilent
    '''
    
    # Write Inno Setup script to file
    with open('cubecad.iss', 'w') as f:
        f.write(inno_script)
    
    # Create output directory for the installer
    if not os.path.exists('installer'):
        os.makedirs('installer')
    
    print("Building installer with Inno Setup...")
    # You'll need to have Inno Setup installed and in your PATH
    # Download from: https://jrsoftware.org/isdl.php
    subprocess.run(['iscc', 'cubecad.iss'])
    
    print("Windows installer created successfully in the 'installer' directory")

if __name__ == "__main__":
    build_windows_installer()
