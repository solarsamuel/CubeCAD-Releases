import sys
import math
import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget, QAction, QToolBar, QToolButton, QTextEdit, QVBoxLayout, QWidget, QLabel, QFileDialog, QMessageBox, QDialog, QGroupBox, QRadioButton, QDialogButtonBox, QTabWidget, QCheckBox, QSizePolicy
from PyQt5.QtCore import Qt, QPoint, QSize
from PyQt5.QtGui import QIcon
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import numpy as np
import re
import xml.etree.ElementTree as ET
import zipfile
import io
import uuid
import os

glutInit()

class Ray:
    def __init__(self, origin, direction):
        self.origin = np.array(origin)
        self.direction = np.array(direction)
        self.direction = self.direction / np.linalg.norm(self.direction)

def ray_cube_intersection(ray, cube_pos):
    # Define the six faces of the cube with Z position
    cube_min = np.array([cube_pos[0], cube_pos[1], cube_pos[2]])
    cube_max = np.array([cube_pos[0] + 1, cube_pos[1] + 1, cube_pos[2] + 1])
    
    t_min = -float('inf')
    t_max = float('inf')
    
    for i in range(3):
        if abs(ray.direction[i]) < 1e-8:
            if ray.origin[i] < cube_min[i] or ray.origin[i] > cube_max[i]:
                return None
        else:
            t1 = (cube_min[i] - ray.origin[i]) / ray.direction[i]
            t2 = (cube_max[i] - ray.origin[i]) / ray.direction[i]
            
            if t1 > t2:
                t1, t2 = t2, t1
                
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            
            if t_min > t_max:
                return None
    
    if t_min < 0:
        if t_max < 0:
            return None
        intersection_point = ray.origin + ray.direction * t_max
    else:
        intersection_point = ray.origin + ray.direction * t_min
        
    # Determine which face was hit
    epsilon = 1e-5
    if abs(intersection_point[2] - cube_pos[2]) < epsilon:
        return ('bottom', intersection_point, t_min if t_min > 0 else t_max)
    elif abs(intersection_point[2] - (cube_pos[2] + 1)) < epsilon:
        return ('top', intersection_point, t_min if t_min > 0 else t_max)
    elif abs(intersection_point[0] - cube_pos[0]) < epsilon:
        return ('left', intersection_point, t_min if t_min > 0 else t_max)
    elif abs(intersection_point[0] - (cube_pos[0] + 1)) < epsilon:
        return ('right', intersection_point, t_min if t_min > 0 else t_max)
    elif abs(intersection_point[1] - cube_pos[1]) < epsilon:
        return ('front', intersection_point, t_min if t_min > 0 else t_max)
    elif abs(intersection_point[1] - (cube_pos[1] + 1)) < epsilon:
        return ('back', intersection_point, t_min if t_min > 0 else t_max)
    return None

class OpenGLGrid(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = (16, 16, 16)  # Added Z dimension
        self.cube_positions = set()  # Will now store (x, y, z) tuples
        self.hover_cell = None
        self.hover_face = None
        self.hover_cube = None
        self.zoom = 1.3
        self.pan_x = -5.0
        self.pan_y = -8.0
        self.rot_x = 0 # Changed initial rotation for better 3D view
        self.rot_y = 0
        self.last_mouse_pos = QPoint()
        self.panning = False
        self.tilting = False
        self.setMouseTracking(True)
        self.placing_mode = True
        #self.export_gcode_mode = False
        self.adjacent_faces = []  # Store adjacent faces for export step mode

        # In the __init__ method of OpenGLGrid, add:
        #self.export_stl_mode = False
        self.export_3mf_mode = False
        
        # Add event log list and reference to main window
        self.event_log = []
        self.main_window = None
        
    # Add a method to set the main window reference
    def set_main_window(self, main_window):
        self.main_window = main_window
     
    def to_user_coords(self, x, y, z):
        """Convert internal 0-based coordinates to user-facing 1-based coordinates"""
        return (x + 1, y + 1, z + 1)
    
    def to_internal_coords(self, x, y, z):
        """Convert user-facing 1-based coordinates to internal 0-based coordinates"""
        return (x - 1, y - 1, z - 1) 
        
    def log_event(self, event_str):
        """Log the event with validation and update the event log display"""
        # Validate event string format
        if re.match(r'^[PE]\(\d+,\d+,\d+\)$', event_str):
            # Add a sequential number and store
            safe_event = f"{len(self.event_log) + 1}:{event_str}"
            self.event_log.append(safe_event)
        
            # Update UI if available
            if self.main_window:
                self.main_window.update_project_log("\n".join(self.event_log))
        else:
            print(f"Rejected invalid event string: {event_str}")   
        

    def set_placing_mode(self):
        self.placing_mode = True
        self.export_3mf_mode = False 

    def set_erasing_mode(self):
        self.placing_mode = False
        self.export_3mf_mode = False 
    
    def set_export_gcode_mode(self):
        print("Export 3MF button clicked!")
        self.placing_mode = False
        self.export_3mf_mode = False

    def set_export_3mf_mode(self):
        self.placing_mode = False
        self.export_3mf_mode = True
        
    def find_part_faces(self, part_cubes):
        """Find all external faces of a part"""
        part_faces = []
    
        for cube in part_cubes:
            x, y, z = cube
            # Check each face of the cube to see if it's external
            # (i.e., doesn't have a neighbor on that side)
        
            # Top face
            if (x, y, z+1) not in part_cubes:
                part_faces.append((cube, 'top'))
        
            # Bottom face
            if (x, y, z-1) not in part_cubes:
                part_faces.append((cube, 'bottom'))
        
            # Left face
            if (x-1, y, z) not in part_cubes:
                part_faces.append((cube, 'left'))
        
            # Right face
            if (x+1, y, z) not in part_cubes:
                part_faces.append((cube, 'right'))
        
            # Front face
            if (x, y-1, z) not in part_cubes:
                part_faces.append((cube, 'front'))
        
            # Back face
            if (x, y+1, z) not in part_cubes:
                part_faces.append((cube, 'back'))
    
        return part_faces
    
    def find_connected_part(self, start_cube):
        """Find all cubes that are connected to form a part"""
        part_cubes = set()
        to_check = {start_cube}
        print(f"Starting connected part search from cube: {start_cube}")
    
        while to_check:
            current = to_check.pop()
            if current not in part_cubes:
                part_cubes.add(current)
                x, y, z = current
            
                # Check all 6 adjacent positions
                neighbors = [
                    (x+1, y, z), (x-1, y, z),  # x axis
                    (x, y+1, z), (x, y-1, z),  # y axis
                    (x, y, z+1), (x, y, z-1)   # z axis
                ]
            
                for neighbor in neighbors:
                    if neighbor in self.cube_positions:
                        to_check.add(neighbor)
                        print(f"Found connected cube at: {neighbor}")
    
        print(f"Found total of {len(part_cubes)} connected cubes")
        return part_cubes

    def generate_3mf_data(self, cubes):
        """Generate 3MF file data for a set of cubes"""
        # Create the main XML structure
        model_root = ET.Element('model', {
            'unit': 'millimeter',
            'xmlns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
        })
    
        # Add resources section
        resources = ET.SubElement(model_root, 'resources')
        object_id = 1
    
        # Create vertices and triangles lists
        vertices = []
        triangles = []
        vertex_count = 0
    
        for cube in cubes:
            x, y, z = cube
            # Scale down to 10%
            #x, y, z = x * 0.1, y * 0.1, z * 0.1
            #size = 0.1  # cube size
        
            # Scale to 10mm (1cm) per cube
            x, y, z = x * 10, y * 10, z * 10
            size = 10  # cube size in millimeters (1cm)
                
            # Add 8 vertices for each cube
            cube_vertices = [
                (x, y, z), (x+size, y, z), (x+size, y+size, z), (x, y+size, z),
                (x, y, z+size), (x+size, y, z+size), (x+size, y+size, z+size), (x, y+size, z+size)
            ]
            vertices.extend(cube_vertices)
        
            # Add 12 triangles (2 per face) for each cube
            cube_triangles = [
                # Bottom face (facing down)
                (0, 2, 1), (0, 3, 2),
                # Top face
                (4, 5, 6), (4, 6, 7),
                # Front face
                (0, 1, 5), (0, 5, 4),
                # Back face
                (2, 3, 7), (2, 7, 6),
                # Left face
                (0, 7, 3), (0, 4, 7),
                # Right face
                (1, 2, 6), (1, 6, 5)
            ]
            # Adjust indices for current cube
            adjusted_triangles = [(a + vertex_count, b + vertex_count, c + vertex_count) 
                            for a, b, c in cube_triangles]
            triangles.extend(adjusted_triangles)
            vertex_count += 8
    
        # Create mesh
        object_elem = ET.SubElement(resources, 'object', {'id': str(object_id), 'type': 'model'})
        mesh = ET.SubElement(object_elem, 'mesh')
    
        # Add vertices
        vertices_elem = ET.SubElement(mesh, 'vertices')
        for v in vertices:
            ET.SubElement(vertices_elem, 'vertex', {
                'x': str(v[0]), 'y': str(v[1]), 'z': str(v[2])
            })
    
        # Add triangles
        triangles_elem = ET.SubElement(mesh, 'triangles')
        for t in triangles:
            ET.SubElement(triangles_elem, 'triangle', {
                'v1': str(t[0]), 'v2': str(t[1]), 'v3': str(t[2])
            })
    
        # Add build section
        build = ET.SubElement(model_root, 'build')
        ET.SubElement(build, 'item', {'objectid': str(object_id)})
    
        # Convert to string
        return ET.tostring(model_root, encoding='utf-8', xml_declaration=True)
    
    def export_3mf(self):
        """Export the currently selected part as a 3MF file with security validation"""
        if self.hover_cube and self.export_3mf_mode:
            try:
                # Get all cubes in the connected part
                part_cubes = self.find_connected_part(self.hover_cube)
            
                # Check for reasonable size
                if len(part_cubes) > 5000:
                    QMessageBox.critical(self, "Error", "Model too complex for export (too many cubes)")
                    return
                
                # Generate 3MF XML data
                model_data = self.generate_3mf_data(part_cubes)
            
                # Open file dialog to save 3MF
                file_name, _ = QFileDialog.getSaveFileName(
                    self, "Save 3MF File", "", "3MF Files (*.3mf);;All Files (*)")
            
                if file_name:
                    # Validate filename to prevent directory traversal
                    safe_filename = os.path.basename(file_name)
                    if not safe_filename.lower().endswith('.3mf'):
                        safe_filename += '.3mf'
                
                    # Create absolute path in the same directory
                    directory = os.path.dirname(file_name)
                    safe_path = os.path.join(directory, safe_filename)
                
                    try:
                        # Create a ZIP file containing the 3MF data
                        with zipfile.ZipFile(safe_path, 'w') as zf:
                            # Add the 3D model XML with validated path
                            zf.writestr('3D/3dmodel.model', model_data)
                        
                            # Add other required files
                            content_types = '''<?xml version="1.0" encoding="UTF-8"?>
                            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />
                                <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />
                            </Types>'''
                            zf.writestr('[Content_Types].xml', content_types)
                        
                            rels_xml = '''<?xml version="1.0" encoding="UTF-8"?>
                            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                                <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
                            </Relationships>'''
                            zf.writestr('_rels/.rels', rels_xml)
                    
                        QMessageBox.information(self, "Success", f"3MF file exported successfully to {safe_path}")
                
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to save 3MF file: {str(e)}")
        
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(1.0, 1.0, 1.0, 1.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / h, 1.0, 200.0)
        glMatrixMode(GL_MODELVIEW)

    def draw_grid(self):
        glColor3f(0.0, 0.0, 0.0)
        glBegin(GL_LINES)
        for i in range(self.grid_size[0] + 1):
            glVertex3f(i, 0, 0)
            glVertex3f(i, self.grid_size[1], 0)
        for j in range(self.grid_size[1] + 1):
            glVertex3f(0, j, 0)
            glVertex3f(self.grid_size[0], j, 0)
        glEnd()

    def draw_cube(self, x, y, z):
        glPushMatrix()
        glTranslatef(x + 0.5, y + 0.5, z + 0.5)
    
        # Draw solid cube (gray)
        glColor3f(0.5, 0.5, 0.5)
        glutSolidCube(1)
    
        # Draw black edges
        glColor3f(0.0, 0.0, 0.0)
        glutWireCube(1.02)
    
        glPopMatrix()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_mouse_pos.x()
        dy = event.y() - self.last_mouse_pos.y()

        # Clear adjacent faces list
        self.adjacent_faces = []

        if self.tilting:
            self.rot_x += dy * 0.5
            self.rot_y += dx * 0.5
        elif self.panning:
            self.pan_x += dx * 0.01
            self.pan_y += -dy * 0.01

        self.makeCurrent()

        viewport = glGetIntegerv(GL_VIEWPORT)
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)

        x = event.x()
        y = viewport[3] - event.y()

        # Get ray origin and direction in world coordinates
        near_x, near_y, near_z = gluUnProject(x, y, 0.0, modelview, projection, viewport)
        far_x, far_y, far_z = gluUnProject(x, y, 1.0, modelview, projection, viewport)
        
        ray_origin = np.array([near_x, near_y, near_z])
        ray_direction = np.array([far_x - near_x, far_y - near_y, far_z - near_z])
        ray = Ray(ray_origin, ray_direction)

        # Reset hover states
        self.hover_cell = None
        self.hover_face = None
        self.hover_cube = None
        
        # Check intersections with all cubes
        nearest_intersection = float('inf')
        for cube_pos in self.cube_positions:
            result = ray_cube_intersection(ray, cube_pos)
            if result:
                face, point, distance = result
                if distance < nearest_intersection:
                    nearest_intersection = distance
                    self.hover_cube = cube_pos
                    self.hover_face = face
            
                    # If in export step mode, find all faces of the connected part
                    if self.export_3mf_mode:
                        part_cubes = self.find_connected_part(cube_pos)
                        self.adjacent_faces = self.find_part_faces(part_cubes)

        # Check grid intersection if no cube was hit or if in placing mode
        if not self.hover_cube or self.placing_mode:
            # Calculate grid intersection
            if abs(ray.direction[2]) > 1e-8:
                t = -ray.origin[2] / ray.direction[2]
                if t > 0:
                    intersection = ray.origin + ray.direction * t
                    grid_x = int(math.floor(intersection[0]))
                    grid_y = int(math.floor(intersection[1]))
                    
                    if 0 <= grid_x < self.grid_size[0] and 0 <= grid_y < self.grid_size[1]:
                        if not self.hover_cube or t < nearest_intersection:
                            self.hover_cell = (grid_x, grid_y)
                            self.hover_cube = None
                            self.hover_face = None

        self.last_mouse_pos = event.pos()
        self.update()

    def set_export_3mf_mode(self):
        self.placing_mode = False
        self.export_3mf_mode = True  # New mode
        
        # Update the draw_highlight method to handle Z position
    def draw_highlight(self, x, y, z, face=None, is_export_highlight=False):
        if face and self.hover_cube:
            glPushMatrix()
            glTranslatef(x + 0.5, y + 0.5, z + 0.5)
        
            if is_export_highlight:
                if self.export_3mf_mode:
                    glColor4f(0.0, 1.0, 0.0, 0.6)  # Green with transparency for STL mode
                else:
                    glColor4f(0.0, 0.5, 1.0, 0.6)  # Blue with transparency for STEP mode
            else:
                glColor4f(1.0, 0.75, 0.8, 0.6)
            
            glBegin(GL_QUADS)
        
            if face == 'top':
                glVertex3f(-0.51, -0.51, 0.51)
                glVertex3f(0.51, -0.51, 0.51)
                glVertex3f(0.51, 0.51, 0.51)
                glVertex3f(-0.51, 0.51, 0.51)
            elif face == 'bottom':
                glVertex3f(-0.51, -0.51, -0.51)
                glVertex3f(0.51, -0.51, -0.51)
                glVertex3f(0.51, 0.51, -0.51)
                glVertex3f(-0.51, 0.51, -0.51)
            elif face == 'front':
                glVertex3f(-0.51, -0.51, -0.51)
                glVertex3f(0.51, -0.51, -0.51)
                glVertex3f(0.51, -0.51, 0.51)
                glVertex3f(-0.51, -0.51, 0.51)
            elif face == 'back':
                glVertex3f(-0.51, 0.51, -0.51)
                glVertex3f(0.51, 0.51, -0.51)
                glVertex3f(0.51, 0.51, 0.51)
                glVertex3f(-0.51, 0.51, 0.51)
            elif face == 'left':
                glVertex3f(-0.51, -0.51, -0.51)
                glVertex3f(-0.51, 0.51, -0.51)
                glVertex3f(-0.51, 0.51, 0.51)
                glVertex3f(-0.51, -0.51, 0.51)
            elif face == 'right':
                glVertex3f(0.51, -0.51, -0.51)
                glVertex3f(0.51, 0.51, -0.51)
                glVertex3f(0.51, 0.51, 0.51)
                glVertex3f(0.51, -0.51, 0.51)
        
            glEnd()
            glPopMatrix()
        else:
            # Draw grid cell highlight at z=0
            glPushMatrix()
            glTranslatef(x + 0.5, y + 0.5, 0.01)
            glColor4f(1.0, 0.75, 0.8, 0.6)  # Pink with transparency

            glBegin(GL_QUADS)
            glVertex3f(-0.5, -0.5, 0)
            glVertex3f(0.5, -0.5, 0)
            glVertex3f(0.5, 0.5, 0)
            glVertex3f(-0.5, 0.5, 0)
            glEnd()

            glPopMatrix()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self.pan_x, self.pan_y, -20 * self.zoom)
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)

        self.draw_grid()
        # Draw axes after grid but before cubes
        self.draw_axes()
        
        for pos in self.cube_positions:
            self.draw_cube(pos[0], pos[1], pos[2])  # Added Z position

        if self.hover_cell or self.hover_cube:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            if self.hover_cube:
                if self.export_3mf_mode:
                    # In export mode, highlight all faces of the part
                    for cube, face in self.adjacent_faces:
                        self.draw_highlight(cube[0], cube[1], cube[2], face, True)
                else:
                    # Normal highlighting for single face
                    self.draw_highlight(self.hover_cube[0], self.hover_cube[1], 
                          self.hover_cube[2], self.hover_face, False)
            else:
                self.draw_highlight(self.hover_cell[0], self.hover_cell[1], 0)
            glDisable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)
            
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.placing_mode:
                if self.hover_cube and self.hover_face:
                    x, y, z = self.hover_cube
                    new_pos = None
        
                    if self.hover_face == 'top' and z + 1 < self.grid_size[2]:
                        new_pos = (x, y, z + 1)
                    elif self.hover_face == 'bottom' and z > 0:
                        new_pos = (x, y, z - 1)
                    elif self.hover_face == 'left' and x > 0:
                        new_pos = (x - 1, y, z)
                    elif self.hover_face == 'right' and x + 1 < self.grid_size[0]:
                        new_pos = (x + 1, y, z)
                    elif self.hover_face == 'front' and y > 0:
                        new_pos = (x, y - 1, z)
                    elif self.hover_face == 'back' and y + 1 < self.grid_size[1]:
                        new_pos = (x, y + 1, z)
        
                    if new_pos and new_pos not in self.cube_positions:
                        self.cube_positions.add(new_pos)
                        # Log the cube placement with 1-based coordinates
                        user_pos = self.to_user_coords(*new_pos)
                        self.log_event(f"P({user_pos[0]},{user_pos[1]},{user_pos[2]})")
            
                elif self.hover_cell:  # Place on ground level
                    new_pos = (self.hover_cell[0], self.hover_cell[1], 0)
                    if new_pos not in self.cube_positions:
                        self.cube_positions.add(new_pos)
                        # Log the cube placement with 1-based coordinates
                        user_pos = self.to_user_coords(*new_pos)
                        self.log_event(f"P({user_pos[0]},{user_pos[1]},{user_pos[2]})")
    
            elif self.export_3mf_mode and self.hover_cube:
                print(f"Exporting STL for part at {self.hover_cube}")
                self.export_3mf()  
                  
            elif not (self.export_3mf_mode): # Only erase if not in export step mode
                if self.hover_cube:
                    # Log the cube erasure before removing it with 1-based coordinates
                    x, y, z = self.hover_cube
                    user_pos = self.to_user_coords(x, y, z)
                    self.log_event(f"E({user_pos[0]},{user_pos[1]},{user_pos[2]})")
                    self.cube_positions.discard(self.hover_cube)
                    self.hover_cube = None
                    self.hover_face = None

        elif event.button() == Qt.RightButton:
            self.tilting = True
        elif event.button() == Qt.MidButton:
            self.panning = True

        self.update()
     
    def mouseReleaseEvent(self, event):
        self.tilting = False
        self.panning = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        if hasattr(self, 'invert_zoom') and self.invert_zoom:
            delta = -delta
        self.zoom = max(0.1, min(self.zoom * math.pow(1.2, delta), 50.0))
        self.update()

    def draw_axes(self):
        """Draw X, Y, Z axes with red, green, blue colors respectively"""
        # Set line width for the axes
        glLineWidth(3.0)
    
        # Draw X axis (Red)
        glBegin(GL_LINES)
        glColor3f(1.0, 0.0, 0.0)  # Red
        glVertex3f(0.0, 0.0, 0.0)  # Origin
        glVertex3f(2.0, 0.0, 0.0)  # 2 units in X direction
        glEnd()
    
        # Draw Y axis (Green)
        glBegin(GL_LINES)
        glColor3f(0.0, 1.0, 0.0)  # Green
        glVertex3f(0.0, 0.0, 0.0)  # Origin
        glVertex3f(0.0, 2.0, 0.0)  # 2 units in Y direction
        glEnd()
    
        # Draw Z axis (Blue)
        glBegin(GL_LINES)
        glColor3f(0.0, 0.0, 1.0)  # Blue
        glVertex3f(0.0, 0.0, 0.0)  # Origin
        glVertex3f(0.0, 0.0, 2.0)  # 2 units in Z direction
        glEnd()
    
        # Create +X label (using a small red rectangle)
        glPushMatrix()
        glTranslatef(2.2, -0.3, 0.0)
        glColor3f(1.0, 0.0, 0.0)  # Red
    
        # Draw "+X" with small rectangles
        # Vertical line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.05, -0.15, 0.0)
        glVertex3f(0.05, -0.15, 0.0)
        glVertex3f(0.05, 0.15, 0.0)
        glVertex3f(-0.05, 0.15, 0.0)
        glEnd()
    
        # Horizontal line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.15, -0.05, 0.0)
        glVertex3f(0.15, -0.05, 0.0)
        glVertex3f(0.15, 0.05, 0.0)
        glVertex3f(-0.15, 0.05, 0.0)
        glEnd()
    
        # Draw X (two crossing lines)
        glTranslatef(0.3, 0.0, 0.0)
        glBegin(GL_QUADS)
        
        glVertex3f(-0.15, -0.15, 0.0)
        glVertex3f(-0.05, -0.15, 0.0)
        glVertex3f(0.15, 0.15, 0.0)
        glVertex3f(0.05, 0.15, 0.0)
        glEnd()
    
        # Second diagonal of X (/)
        glBegin(GL_QUADS)
        glVertex3f(-0.15, 0.15, 0.0)
        glVertex3f(-0.05, 0.15, 0.0)
        glVertex3f(0.15, -0.15, 0.0)
        glVertex3f(0.05, -0.15, 0.0)
        glEnd()
    
        glPopMatrix()
    
        # Draw +Y label
        glPushMatrix()
        glTranslatef(-0.6, 2.2, 0.0)
        glColor3f(0.0, 1.0, 0.0)  # Green
    
        # Draw + symbol for Y
        # Vertical line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.05, -0.15, 0.0)
        glVertex3f(0.05, -0.15, 0.0)
        glVertex3f(0.05, 0.15, 0.0)
        glVertex3f(-0.05, 0.15, 0.0)
        glEnd()
    
        # Horizontal line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.15, -0.05, 0.0)
        glVertex3f(0.15, -0.05, 0.0)
        glVertex3f(0.15, 0.05, 0.0)
        glVertex3f(-0.15, 0.05, 0.0)
        glEnd()
    
        # Draw Y
        glTranslatef(0.3, 0.0, 0.0)
    
        # Right arm of Y (\)
        glBegin(GL_QUADS)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.1, 0.0, 0.0)
        glVertex3f(0.2, 0.2, 0.0)
        glVertex3f(0.1, 0.2, 0.0)
        glEnd()
    
        # Left arm of Y (/)
        glBegin(GL_QUADS)
        glVertex3f(0.0, 0.2, 0.0)
        glVertex3f(-0.1, 0.2, 0.0)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.1, 0.0, 0.0)
        glEnd()
    
        # Stem of Y
        glBegin(GL_QUADS)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.1, 0.0, 0.0)
        glVertex3f(0.1, -0.2, 0.0)
        glVertex3f(0.0, -0.2, 0.0)
        glEnd()
    
        glPopMatrix()
    
        # Draw +Z label (optional)
        glPushMatrix()
        glTranslatef(-0.5, 0.0, 2.2)
        glRotatef(90, 1.0, 0.0, 0.0)  # Rotate to put in X-Z plane
        glColor3f(0.0, 0.0, 1.0)  # Blue
    
        # Draw + symbol for Z
        # Vertical line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.05, -0.15, 0.0)
        glVertex3f(0.05, -0.15, 0.0)
        glVertex3f(0.05, 0.15, 0.0)
        glVertex3f(-0.05, 0.15, 0.0)
        glEnd()
    
        # Horizontal line of +
        glBegin(GL_QUADS)
        glVertex3f(-0.15, -0.05, 0.0)
        glVertex3f(0.15, -0.05, 0.0)
        glVertex3f(0.15, 0.05, 0.0)
        glVertex3f(-0.15, 0.05, 0.0)
        glEnd()
    
        # Draw Z
        glTranslatef(0.3, 0.0, 0.0)
       
        # Top horizontal of Z
        glBegin(GL_QUADS)
        glVertex3f(-0.15, 0.15, 0.0)
        glVertex3f(0.15, 0.15, 0.0)
        glVertex3f(0.15, 0.05, 0.0)
        glVertex3f(-0.15, 0.05, 0.0)
        glEnd()
        
        # Additional diagonal piece for more thickness
        glBegin(GL_QUADS)
        glVertex3f(0.16, 0.09, 0.0)   # Top-right corner
        glVertex3f(0.04, -0.05, 0.0)   # Mid-right above
        glVertex3f(0.10, 0.15, 0.0) # Mid-left above
        glVertex3f(-0.15, -0.05, 0.0) # Bottom-left
        glEnd()
        
         # Bottom horizontal of Z
        glBegin(GL_QUADS)
        glVertex3f(-0.15, -0.05, 0.0)
        glVertex3f(0.15, -0.05, 0.0)
        glVertex3f(0.15, -0.15, 0.0)
        glVertex3f(-0.15, -0.15, 0.0)
        glEnd()
        
        glPopMatrix()
    
        # Reset line width to default
        glLineWidth(1.0)

    #UPLOAD PROJECT LOG IN GRID
    def load_project_log(self, filepath):
        try:
            # Limit file size to prevent resource exhaustion
            MAX_FILE_SIZE = 1024 * 1024  # 1 MB limit
            file_size = os.path.getsize(filepath)
            if file_size > MAX_FILE_SIZE:
                QMessageBox.critical(self, "Error", f"Project log file too large: {file_size} bytes (max: {MAX_FILE_SIZE} bytes)")
                return

            with open(filepath, "r") as file:
                lines = file.readlines()
                if len(lines) > 100000:  # Limit number of lines
                    QMessageBox.critical(self, "Error", "Project log file contains too many lines")
                    return
                print("Reading project log file")

            self.event_log = []
            self.cube_positions.clear()
            print("Old cubes cleared")
        
            # Limit maximum number of cubes for security
            MAX_CUBES = 100000
            cube_count = 0

            for i, line in enumerate(lines):
                # Validate line length
                if len(line) > 100000:
                    print(f"Skipping excessively long line {i+1}")
                    continue
                
                # Extract both P(x,y,z) and E(x,y,z) separately
                place_matches = re.findall(r'P\((\d+),(\d+),(\d+)\)', line)
                erase_matches = re.findall(r'E\((\d+),(\d+),(\d+)\)', line)
            
                # Limit the number of matches processed in one line
                if len(place_matches) > 100 or len(erase_matches) > 100:
                    print(f"Skipping line {i+1}: too many operations in a single line")
                    continue

                # Handle P(x,y,z) (Adding cubes)
                for match in place_matches:
                    try:
                        # Validate integers are in reasonable range
                        user_x, user_y, user_z = int(match[0]), int(match[1]), int(match[2])
                    
                        # Prevent integer overflow attacks by limiting values
                        if (user_x > 1000 or user_y > 1000 or user_z > 1000 or 
                            user_x < 0 or user_y < 0 or user_z < 0):
                            print(f"Invalid coordinates detected: ({user_x}, {user_y}, {user_z})")
                            continue
                        
                        # Convert to 0-based internal coordinates
                        x, y, z = self.to_internal_coords(user_x, user_y, user_z)
                    
                        # Ensure position is within grid bounds
                        if (0 <= x < self.grid_size[0] and 
                            0 <= y < self.grid_size[1] and 
                            0 <= z < self.grid_size[2]):
                        
                            # Check for cube count limits
                            if cube_count >= MAX_CUBES:
                                QMessageBox.warning(self, "Warning", f"Maximum cube limit ({MAX_CUBES}) reached")
                                break
                            
                            self.cube_positions.add((x, y, z))
                            cube_count += 1
                        
                            # Create a sanitized log entry
                            safe_entry = f"{len(self.event_log) + 1}:P({user_x},{user_y},{user_z})"
                            self.event_log.append(safe_entry)
                        else:
                            print(f"Invalid grid position: ({x}, {y}, {z})")
                    except ValueError:
                        print(f"Error parsing placement line {i+1}: {match}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project log: {str(e)}")

    def apply_settings(self, settings):
        """Apply settings to this widget"""
        self.invert_zoom = settings.get('invert_zoom', False)
        # Apply any other settings
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CubeCAD V1.0")
        self.setGeometry(100, 100, 1000, 600)
        
        # Create icons for Place Cube button states
        
        save_project_path = "save_project_log.png"
        upload_project_path = "upload_project_log.png"
        place_cube_active_path = "place_cube_active.png"
        place_cube_inactive_path = "place_cube_inactive.png"
        erase_cube_active_path = "erase_cube_active.png"
        erase_cube_inactive_path = "erase_cube_inactive.png"
        export_3MF_path = "export_3MF.png"
        settings_path = "settings.png"
        
        # Debug icon loading
        print(f"Save Project icon path exists: {os.path.exists(save_project_path)}")
        print(f"Upload Project icon path exists: {os.path.exists(upload_project_path)}")
        print(f"Place Cube active icon full path exists: {os.path.exists(place_cube_active_path)}")
        print(f"Place Cube Inactive icon full path exists: {os.path.exists(place_cube_inactive_path)}")
        print(f"Erase Cube active icon path exists: {os.path.exists(erase_cube_active_path )}")
        print(f"Erase Cube Inactive icon path exists: {os.path.exists(erase_cube_inactive_path)}")
        print(f"Export 3MF full path exists: {os.path.exists(export_3MF_path)}")
        print(f"settings path exists: {os.path.exists(settings_path)}")
        
        print(f"   ")
        
        print(f"Save Project icon path exists: {os.path.abspath(save_project_path)}")
        print(f"Upload Project icon path exists: {os.path.abspath(upload_project_path)}")
        print(f"Place Cube active icon full path exists: {os.path.abspath(place_cube_active_path)}")
        print(f"Place Cube Inactive icon full path exists: {os.path.abspath(place_cube_inactive_path)}")
        print(f"Erase Cube active icon path exists: {os.path.abspath(erase_cube_active_path )}")
        print(f"Erase Cube Inactive icon path exists: {os.path.abspath(erase_cube_inactive_path)}")
        print(f"Export 3MF full path exists: {os.path.abspath(export_3MF_path)}")
        print(f"settings path exists: {os.path.abspath(settings_path)}")
        
        # Create icons for Place Cube button states        
        self.save_project = QIcon(save_project_path)  
        self.upload_project = QIcon(upload_project_path) 
        self.place_cube_active = QIcon(place_cube_active_path)  
        self.place_cube_inactive = QIcon(place_cube_inactive_path) 
        self.erase_cube_active = QIcon(erase_cube_active_path)  
        self.erase_cube_inactive = QIcon(erase_cube_inactive_path) 
        self.export_3MF = QIcon(export_3MF_path)  
        self.settings_icon = QIcon(settings_path)
        
        # Check if icons are valid/loaded        
        print(f"Place Cube active icon is null: {self.place_cube_active.isNull()}")
        print(f"Place cube Inactive icon is null: {self.place_cube_inactive.isNull()}")

        # Create the OpenGL widget
        self.opengl_grid = OpenGLGrid()
        # Set main window reference for logging
        self.opengl_grid.set_main_window(self)        
    
        # Create project log widgets
        self.event_log_widget = QTextEdit()
        self.event_log_widget.setStyleSheet("background-color: #f0f0f0;")
        self.event_log_label = QLabel("Project Log")
        self.event_log_widget.setReadOnly(True)
    
        # Create container for log widgets
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.event_log_label)
        log_layout.addWidget(self.event_log_widget, 1)
        log_container = QWidget()
        log_container.setLayout(log_layout)
    
        # Main layout with OpenGL and log
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.opengl_grid, 10)
        main_layout.addWidget(log_container)
    
        # Create central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Initialize settings dictionary (renamed from self.settings to self.settings_dict)
        self.settings_dict = {'invert_zoom': False}

        # Initialize UI (which will create toolbar and buttons)
        self.initUI()

    def initUI(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Set the icon size for the toolbar
        toolbar.setIconSize(QSize(64, 64))

        # Save Project Log button (far left)
        self.save_log_action = QAction("Save Project Log", self)
        self.save_log_action.setToolTip("Save Project Log")
        self.save_log_action.triggered.connect(self.save_project_log)
        toolbar.addAction(self.save_log_action)

        # Upload Project Log button (second from left)
        self.upload_log_action = QAction("Upload Project Log", self)
        self.upload_log_action.setToolTip("Upload Project Log")
        self.upload_log_action.triggered.connect(self.upload_project_log)
        toolbar.addAction(self.upload_log_action)

        # Place Cube button (third from left)
        self.place_action = QAction("Place Cube", self)
        self.place_action.setToolTip("Place Cube")  # Add tooltip here
        self.place_action.triggered.connect(self.set_placing_mode)
        toolbar.addAction(self.place_action)

        # Erase Cube button (fourth from left)
        self.erase_action = QAction("Erase Cube", self)
        self.erase_action.setToolTip("Erase Cube")
        self.erase_action.triggered.connect(self.set_erasing_mode)
        toolbar.addAction(self.erase_action)
        
        self.export_3mf_action = QAction("Export 3MF", self)  
        self.export_3mf_action.setToolTip("Export as 3MF") 
        self.export_3mf_action.triggered.connect(self.set_export_3mf_mode)  
        toolbar.addAction(self.export_3mf_action)
    
        # Settings button (right-most)
        self.settings_action = QAction("Settings", self)
        self.settings_action.setToolTip("Settings")
        self.settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(self.settings_action)
        
        # In initUI method, update the hint label creation:
        self.hint_label = QLabel("")  # Empty by default
        self.hint_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px; margin-left: 10px;")
        toolbar.addWidget(self.hint_label)

        # Store action buttons
        self.save_log_button = toolbar.widgetForAction(self.save_log_action)
        self.upload_log_button = toolbar.widgetForAction(self.upload_log_action)
        self.place_button = toolbar.widgetForAction(self.place_action)
        self.erase_button = toolbar.widgetForAction(self.erase_action)
        self.export_3mf_button = toolbar.widgetForAction(self.export_3mf_action)
        self.settings_button = toolbar.widgetForAction(self.settings_action)

        self.update_button_styles()
        
        # Initialize settings
        self.settings = {'invert_zoom': False}

    def set_placing_mode(self):
        self.opengl_grid.set_placing_mode()
        self.update_button_styles()
        self.hint_label.setText("")

    def set_erasing_mode(self):
        self.opengl_grid.set_erasing_mode()
        self.update_button_styles()
        self.hint_label.setText("")

    def set_export_3mf_mode(self):
        self.opengl_grid.set_export_3mf_mode()
        self.update_button_styles()
        # Show the hint only when in 3MF export mode
        print("Setting hint label visible")
        self.hint_label.setText("HINT: Hover over the part and click it to export 3MF")
        print("Hint label visible state:", self.hint_label.isVisible())
        print("Export 3MF mode activated - end")

    def update_button_styles(self):
        """Update button styles based on current mode"""
        # Reset all buttons
        self.place_button.setStyleSheet("")
        self.erase_button.setStyleSheet("")
        self.export_3mf_button.setStyleSheet("")  

        # Update Place Cube button icon based on state
        if self.opengl_grid.placing_mode:
            self.place_action.setIcon(self.place_cube_active)
            print("Setting active icon")
        else:
            self.place_action.setIcon(self.place_cube_inactive)
            print("Setting inactive icon")
          
        # Update Erase Cube button icon based on state
        if not self.opengl_grid.placing_mode and not self.opengl_grid.export_3mf_mode:
            # This is effectively the erasing mode
            self.erase_action.setIcon(self.erase_cube_active)
            print("Setting erase active icon")
        else:
            self.erase_action.setIcon(self.erase_cube_inactive)
            print("Setting erase inactive icon")  
        
        # Set icons for other buttons too
        self.save_log_action.setIcon(self.save_project)
        self.upload_log_action.setIcon(self.upload_project)
        self.export_3mf_action.setIcon(self.export_3MF)
        self.settings_action.setIcon(self.settings_icon)

        # Force icon to be visible by setting empty text
        self.place_action.setText("")
        self.erase_action.setText("")
        self.save_log_action.setText("")
        self.upload_log_action.setText("")
        self.export_3mf_action.setText("")
        self.settings_action.setText("")

        # Highlight active button
        if self.opengl_grid.placing_mode:
            self.place_button.setStyleSheet("background-color: darkgray; color: white;")
        elif self.opengl_grid.export_3mf_mode:
            self.export_3mf_button.setStyleSheet("background-color: darkgray; color: white;")
        else:
            self.erase_button.setStyleSheet("background-color: darkgray; color: white;")

    def update_project_log(self, text):
        self.event_log_widget.setPlainText(text)
        
    def save_project_log(self):
        # Clear the hint label
        self.hint_label.setText("") 
        
        try:
            filename = datetime.datetime.now().strftime("project_log_%Y-%m-%d_%H-%M-%S.txt")
            options = QFileDialog.Options()
            filepath, _ = QFileDialog.getSaveFileName(self, "Save Project Log", filename, 
                                               "Text Files (*.txt);;All Files (*)", options=options)
        
            if filepath:
                # Sanitize content before saving
                log_content = self.event_log_widget.toPlainText()
            
                # Basic sanitization - only allow specific log entry formats
                sanitized_lines = []
                for line in log_content.split('\n'):
                    # Only accept lines matching our expected format
                    if re.match(r'^\d+:P\(\d+,\d+,\d+\)$', line) or re.match(r'^\d+:E\(\d+,\d+,\d+\)$', line):
                        sanitized_lines.append(line)
                    else:
                        print(f"Removed potentially unsafe log line: {line}")
            
                sanitized_content = '\n'.join(sanitized_lines)
            
                # Write the sanitized content to file
                with open(filepath, "w") as file:
                    file.write(sanitized_content)
                
                QMessageBox.information(self, "Success", "Project log saved successfully")
            
            # Clear the hint label
            #self.hint_label.setText("")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project log: {str(e)}")
   

    #UPLOAD PROJECT LOG FILE DIALOG           
    def upload_project_log(self):
        # Clear the hint label
        self.hint_label.setText("") 
        
        """Upload a Project Log file and update the scene accordingly."""
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Project Log", "", "Text Files (*.txt);;All Files (*)", options=options)
    
        if filepath:
            self.opengl_grid.load_project_log(filepath)
        
    def show_settings(self):
        # Clear the hint label
        self.hint_label.setText("") 
        
        """Show the settings dialog and apply any changes"""
        dialog = Settings(self, self.settings_dict)
        if dialog.exec_():  # Dialog accepted
            self.settings_dict = dialog.get_settings()
            self.apply_settings()

    def apply_settings(self):
        """Apply the current settings to the application"""
        # Pass settings to the OpenGL widget
        self.opengl_grid.apply_settings(self.settings_dict)

class Settings(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 600)  # Make the dialog bigger to accommodate tabs
        
        # Store current settings or initialize with defaults
        self.current_settings = current_settings or {}
        
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Create individual tab widgets
        cad_tab = QWidget()
        about_tab = QWidget() 
        
        # Add tabs to tab widget
        tabs.addTab(cad_tab, "CAD Settings")
        tabs.addTab(about_tab, "About")
        
        # Create layouts for each tab
        cad_layout = QVBoxLayout()
        about_layout = QVBoxLayout() 
        
        # CAD Settings Tab
        cad_group = QGroupBox("Mouse Settings")
        cad_group_layout = QVBoxLayout()
        
        # Add invert mouse zoom checkbox
        self.invert_zoom = QCheckBox("Invert Mouse Zoom")
        if 'invert_zoom' in self.current_settings:
            self.invert_zoom.setChecked(self.current_settings['invert_zoom'])
        cad_group_layout.addWidget(self.invert_zoom)
        
        cad_group.setLayout(cad_group_layout)
        cad_layout.addWidget(cad_group)
        cad_layout.addStretch()
        cad_tab.setLayout(cad_layout)
        
        # About Tab
        about_label = QLabel("Mission: CubeCAD aims to get kids building 3D models in minutes.")
        about_label.setWordWrap(True)  # Enable word wrapping
        about_label.setStyleSheet("font-size: 12pt; margin: 20px;")  # Make text larger and add margins
        about_layout.addWidget(about_label)
        about_layout.addStretch()  # Add stretch to keep content at top
        about_tab.setLayout(about_layout)
        
        # Add tab widget to main layout
        main_layout.addWidget(tabs)
        
        # OK and Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
        
    def get_settings(self):
        # Return the current settings from the dialog widgets
        return {
            'invert_zoom': self.invert_zoom.isChecked()
        }
        
class SecurityValidator:
    @staticmethod
    def validate_coords(x, y, z, min_val=0, max_val=1000):
        """Validate coordinate values are within reasonable bounds"""
        try:
            # Ensure values are integers
            x, y, z = int(x), int(y), int(z)
            
            # Check range
            if (min_val <= x <= max_val and 
                min_val <= y <= max_val and 
                min_val <= z <= max_val):
                return True, (x, y, z)
            else:
                return False, None
        except (ValueError, TypeError):
            return False, None
            
    @staticmethod
    def sanitize_filename(filename):
        """Remove potentially unsafe characters from filenames"""
        # Allow only alphanumeric, underscore, hyphen, period
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        return ''.join(c for c in filename if c in safe_chars)
    
    @staticmethod
    def validate_log_line(line):
        """Validate a log line matches expected format"""
        return (re.match(r'^\d+:P\(\d+,\d+,\d+\)$', line) or 
                re.match(r'^\d+:E\(\d+,\d+,\d+\)$', line))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    #Q29weXJpZ2h0IFNhbSBXZWNoc2xlcg==
