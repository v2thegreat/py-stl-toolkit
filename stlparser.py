"""
This module provides basic STL parsing, saving, displaying, and post-processing capabilities

File format described at http://people.sc.fsu.edu/~jburkardt/data/stlb/stlb.html
Bytecount described at http://en.wikipedia.org/wiki/STL_(file_format)
Help and original code from: http://stackoverflow.com/questions/7566825/python-parsing-binary-stl-file
"""
import stl
from stl import mesh

import struct
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import sys

#TODO: Figure out what these values are
SCALE_INCH = 1.0
SCALE_CM = 1.0

SQRT_TWO = 1.41421356237

class SolidSTL(object):

    def __init__(self, title=None, triangles=None, norms=None, bytecount=None):

        if not triangles:
            triangles = []

        if not norms:
            norms = []
            
        self.title = title
        self.triangles = triangles
        self.norms = norms
        self.bytecount = bytecount

        self.faces = self.__getFaces()
        self.vertices = self.__getVertices()
        self.edges = self.__getEdges()

    def mergeSolid(self, stlsolid):
        self.addTriangles(stlsolid.triangles, stlsolid.norms)

    def addTriangles(self, triangles, norms):
        self.triangles.extend(triangles)
        self.norms.extend(norms)
        
        # Update all the values
        self.faces = self.__getFaces()
        self.vertices = self.__getVertices()
        self.edges = self.__getEdges()

    def iterTriangles(self):
        for i in range(len(self.triangles)):
            yield self.triangles[i], self.norms[i]

    def __getEdges(self):
        """
        WARNING: THIS IS THE NUMBER OF TRIANGLE EDGES, NOT THE OVERALL EDGES OF THE SOLID
        """
        def getSortedEdges(triangle):
            edges = set()
            for vertex1 in triangle:
                for vertex2 in triangle:
                    if not vertex1 == vertex2:
                        # lexicographical comparison
                        edge = ((vertex1, vertex2), (vertex2, vertex1))[vertex1 > vertex2]
                        edges.add(edge)
            return edges

        self.edges = set()
        for triangle in self.triangles:
            tri_edges = getSortedEdges(triangle)
            self.edges.update(tri_edges)
        
        return self.edges
    
    def __getFaces(self):
        """
        WARNING: THIS IS THE NUMBER OF TRIANGLE EDGES, NOT THE OVERALL EDGES OF THE SOLID
        """
        return self.triangles

    def __getVertices(self):
        """
        WARNING: THIS IS THE NUMBER OF TRIANGLE EDGES, NOT THE OVERALL EDGES OF THE SOLID
        """
        self.vertices = set()
        for triangle in self.triangles:
            for vertex in triangle:
                self.vertices.add(vertex)

        return self.vertices

def createVerticalCuboid(topPoint, edgeLength=1.0):
    """
    Creates a cuboid structure, with triangles,
    the tops and bottoms of the cuboid will be removed,
    the sides of the top and bottom surfaces are parallel with the X-Y axes
    """
    #WARNING: The order that these points are created and listed matter
    # so that normals can be computed in the proper direction

    # create the 8 points
    e2 = edgeLength/2.0
    point = np.array(topPoint)
    topSurface = np.array([
            point + [-e2, e2, 0],
            point + [e2, e2, 0],
            point + [e2, -e2, 0],
            point + [-e2, -e2, 0]
            ])

    bottomMask = np.tile( [1,1,0], [4,1] )    
    bottomSurface = np.multiply(bottomMask, topSurface)

    topSurface = list(map(lambda x: tuple(x), topSurface))
    bottomSurface = list(map(lambda x: tuple(x), bottomSurface))
    
    # join the 8 points as 8 triangles
    triangles = []
    for i in range(len(topSurface)):
        # These must be listed in clockwise fashion in relation to the face's normal, using the RHR
        triangles.append( (topSurface[i], bottomSurface[i], bottomSurface[(i+1) % 4]) )
        triangles.append( (bottomSurface[(i+1) % 4], topSurface[(i+1) % 4], topSurface[i]) )
    
    # convert to tuples
    triangles = map(lambda x: tuple(x), triangles)

    # compute the normals
    norms = []
    for triangle in triangles:
        norms.append(__computeTriangleNormal(triangle))
    
    return (triangles, norms)

def __computeTriangleNormal(triangle):
    """
    Uses the cross product of the vectors formed by the triangle's vertices
    """
    vec1 = np.array(triangle[0]) - np.array(triangle[1])
    vec2 = np.array(triangle[2]) - np.array(triangle[1])
    return tuple(np.cross(vec1, vec2))

def addCuboidSupports(stlsolid, area=1.0):

    # iterate through each triangle and add supports to the stlsolid
    for triangle, norm in stlsolid.iterTriangles():
        centroid = __getTriangleCentroid(triangle)
        supportDirs = __getSupportDirection(centroid, norm, 10)
        if not supportDirs is None:
            triangles, norms = createVerticalCuboid(centroid)
            stlsolid.addTriangles(triangles, norms)

def rotate(theta, axis="x", units="degrees"):
    pass

def stretch():
    pass

def isSimple(stlsolid):
    """
    Uses Euler's formula for polyhedron's to determine if the 
    solid is simple (has no "holes" and is convex)
    
    In short, verifies: V - E + F = 2
    """
    
    if not isinstance(stlsolid, SolidSTL):
        raise TypeError("Incorrect type, expected stlparser.SolidSTL")

    V = len(stlsolid.vertices)
    E = len(stlsolid.edges)
    F = len(stlsolid.faces)
    return V - E + F == 2
    
def __getNormalLine(origin, vector, scale=1.0):
    """
    Returns a plottable line represented by a 3-tuple where each element is an array
    for a single axis. First element is all x-coordinates, second is all y-coordinates, etc...
    """
    vector = np.array(vector) * scale
    endpoint = tuple([sum(el) for el in zip(origin, vector)])
    return tuple([np.linspace(start, stop, 10) for start, stop in zip(origin, endpoint)])

def __getTriangleCentroid(triangle):
    """
    Returns the centroid of a triangle in 3D-space
    """
    # group the xs, ys, and zs
    coordGroups = zip(triangle[0], triangle[1], triangle[2])
    centroid = tuple([sum(coordGroup)/3.0 for coordGroup in coordGroups])
    return centroid

def __getSupportDirection(origin, vector, scale=1.0):
    z = vector[2]
    
    if z < 0:
        down = [0, 0, -1]
        return __getNormalLine(origin, down, scale)
    # Does not require support material, don't plot anything
    return None
    
def display(stlsolid, file, showNorms=True, showSupportDirections=False):
    """
    Renders the solid and normal vectors using matplotlib
    """
    fig = plt.figure()
    #ax = Axes3D(fig)
    ax = fig.gca(projection='3d')
    mesh_body = mesh.Mesh.from_file(file)
    
    dimentions = find_mins_maxs(mesh_body)
    min_dimentions = min(dimentions)
    max_dimentions = max(dimentions)

    ax.set_xlim(min_dimentions, max_dimentions)
    ax.set_ylim(min_dimentions, max_dimentions)
    ax.set_zlim(min_dimentions, max_dimentions)
    ax.grid(False)
    ax.set_axis_off()

    triangles = stlsolid.triangles
    norms = stlsolid.norms

    for i in range(len(triangles)):
            
        triangle = triangles[i]
       
        face = Poly3DCollection([triangle])
        face.set_alpha(0.5)
        ax.add_collection3d(face)

        if showNorms or showSupportDirections:
            centroid = __getTriangleCentroid(triangle)
            norm = norms[i]
            
            if showNorms:
                xs, ys, zs = __getNormalLine(centroid, norm, 10)
                ax.plot(xs, ys, zs)

            if showSupportDirections:
                supportDirs = __getSupportDirection(centroid, norm, 10)
                if not supportDirs is None:
                    xs, ys, zs = supportDirs
                    ax.plot(xs, ys, zs)
    plt.tight_layout()
    plt.show()

def loadBSTL(bstl):
    """
    Loads triangles from file, input can be a file path or a file handler
    Returns a SolidSTL object
    """
    """
    if isinstance(bstl, file):
        f = bstl
    """
    if isinstance(bstl, str):
        f = open(bstl, 'rb')
    else:
        raise TypeError("must be a string or file")
    
    header = f.read(80)
    numTriangles = struct.unpack("@i", f.read(4))
    numTriangles = numTriangles[0]
    
    triangles = [(0,0,0)]*numTriangles # prealloc, slightly faster than append
    norms = [(0,0,0)]*numTriangles
    bytecounts = [(0,0,0)]*numTriangles
    
    for i in range(numTriangles):
        # facet records
        norms[i] = struct.unpack("<3f", f.read(12))
        vertex1 = struct.unpack("<3f", f.read(12))
        vertex2 = struct.unpack("<3f", f.read(12))
        vertex3 = struct.unpack("<3f", f.read(12))
        bytecounts[i] = struct.unpack("H", f.read(2)) # not sure what this is

        triangles[i] = (vertex1, vertex2, vertex3)
    
    return SolidSTL(header, triangles, norms, bytecounts)

def __shiftUp(stlsolid, amt=5.0):
    """
    This is purely for testing purposes (force a situation where supports are needed),
    not really sure why anybody would actually use this
    """
    for i in range(len(stlsolid.triangles)):
        triangle = list(stlsolid.triangles[i])

        for v in range(len(triangle)):
            triangle[v] = list(triangle[v])
            triangle[v][2] += amt
            triangle[v] = tuple(triangle[v])

        stlsolid.triangles[i] = tuple(triangle)

def loadSTL(infilename):

    with open(infilename,'r') as f:
        name = f.readline().split()
        if not name[0] == "solid":
            raise IOError("Expecting first input as \"solid\" [name]")
        
        if len(name) == 2:
            title = name[1]
        elif len(name) == 1:
            title = None
        else:
            raise IOError("Too many inputs to first line")
        
        triangles = []
        norms = []

        for line in f:
            params = line.split()
            cmd = params[0]
            if cmd == "endsolid":
                if name and params[1] == name:
                    break
                else: #TODO: inform that name needs to be there
                    break
            elif cmd == "facet":
                norm = map(float, params[2:5])
                norms.append(tuple(norm))
            elif cmd == "outer":
                triangle = []
            elif cmd == "vertex":
                vertex = map(float, params[1:4])
                triangle.append(tuple(vertex))
            elif cmd == "endloop":
                continue
            elif cmd == "endfacet":
                triangles.append(tuple(triangle)) #TODO: Check IO formatting
                triangle = []

        return SolidSTL(title, triangles, norms)

# from (will be modified soon)
# http://stackoverflow.com/questions/7566825/python-parsing-binary-stl-file    
def saveSTL(stlsolid, outfilename):
    """
    Saves the solid in standard STL format
    """

    if not isinstance(stlsolid, SolidSTL):
        raise TypeError("Must be of type SolidSTL")

    triangles = stlsolid.triangles
    norms = stlsolid.norms

    with open(outfilename, "w") as f:

        f.write("solid "+outfilename+"\n")
        for i in range(len(triangles)):
            norm = norms[i]
            triangle = triangles[i]
            f.write("facet normal %f %f %f\n"%(norm))
            f.write("outer loop\n")
            f.write("vertex %f %f %f\n"%triangle[0])
            f.write("vertex %f %f %f\n"%triangle[1])
            f.write("vertex %f %f %f\n"%triangle[2])
            f.write("endloop\n")
            f.write("endfacet\n")
        f.write("endsolid "+outfilename+"\n")

def find_mins_maxs(obj):
    """
    Brutally plagarised from numpy-stl: https://github.com/WoLpH/numpy-stl
    """

    minx = maxx = miny = maxy = minz = maxz = None
    for p in obj.points:
        # p contains (x, y, z)
        if minx is None:
            minx = p[stl.Dimension.X]
            maxx = p[stl.Dimension.X]
            miny = p[stl.Dimension.Y]
            maxy = p[stl.Dimension.Y]
            minz = p[stl.Dimension.Z]
            maxz = p[stl.Dimension.Z]
        else:
            maxx = max(p[stl.Dimension.X], maxx)
            minx = min(p[stl.Dimension.X], minx)
            maxy = max(p[stl.Dimension.Y], maxy)
            miny = min(p[stl.Dimension.Y], miny)
            maxz = max(p[stl.Dimension.Z], maxz)
            minz = min(p[stl.Dimension.Z], minz)
    return minx, maxx, miny, maxy, minz, maxz

if __name__ == "__main__":
    model = loadBSTL(sys.argv[1])
    # file  = r"C:\Users\aliab\Google Drive\Work\W.O.L.F\ARM\Arm Lower Base\STL File\Arm Base-1.STL"
    # model = loadBSTL(file)
    __shiftUp(model,5)
    addCuboidSupports(model)
    display(model, file = sys.argv[1], showNorms = False, showSupportDirections = False)
